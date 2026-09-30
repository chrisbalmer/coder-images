#!/usr/bin/env python3
"""Resolve `<image>:<version>` references to registry digests over the OCI API.

Stdlib only (no curl, no jq, no docker, no skopeo) so GitHub runners and Gitea runners
behave identically. Reads a JSON array of `"base:1.1.5"` style references on stdin and
writes a JSON object mapping each reference to its digest on stdout.

A dependent must never be published against a base version that cannot be pinned, so any
unresolvable reference is reported and the exit status is non-zero.

Usage:
  echo '["base:2.0.0"]' | base-digest.py --registry ghcr.io --owner chrisbalmer
  echo '["base:2.0.0"]' | base-digest.py --registry registry.example.com --owner library \
      --username me --password "$TOKEN"
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from base64 import b64encode

ACCEPT = ",".join(
    (
        "application/vnd.docker.distribution.manifest.list.v2+json",
        "application/vnd.docker.distribution.manifest.v2+json",
        "application/vnd.oci.image.index.v1+json",
        "application/vnd.oci.image.manifest.v1+json",
        "application/vnd.docker.distribution.manifest.v1+json",
    )
)
TIMEOUT = 30


class ResolveError(Exception):
    pass


def request(url: str, headers: dict | None = None):
    req = urllib.request.Request(url, headers=headers or {})
    return urllib.request.urlopen(req, timeout=TIMEOUT)


def challenge(registry: str) -> tuple[str, dict]:
    """The token realm and its parameters, from the registry's own WWW-Authenticate challenge.

    ghcr.io serves tokens at /token, Harbor at /service/token with service=harbor-registry, and
    the registry says which; asking beats hardcoding one registry's layout.
    """
    try:
        with request(f"https://{registry}/v2/"):
            return "", {}  # open registry: no token needed
    except urllib.error.HTTPError as exc:
        header = exc.headers.get("WWW-Authenticate", "")
    except (urllib.error.URLError, OSError) as exc:
        raise ResolveError(f"cannot reach {registry}: {exc}") from exc
    scheme, _, rest = header.partition(" ")
    if scheme.lower() != "bearer":
        raise ResolveError(f"{registry} does not offer bearer auth ({header or 'no challenge'})")
    params = dict(re.findall(r'(\w+)="([^"]*)"', rest))
    realm = params.pop("realm", "")
    if not realm:
        raise ResolveError(f"{registry} sent a bearer challenge with no realm")
    params.pop("scope", None)
    return realm, params


def bearer(registry: str, repository: str, username: str, password: str) -> str:
    """Pull token for one repository: anonymous, or basic auth when credentials are supplied.

    Empty when the registry needs no token at all.
    """
    realm, params = challenge(registry)
    if not realm:
        return ""
    headers = {}
    if username and password:
        headers["Authorization"] = "Basic " + b64encode(f"{username}:{password}".encode()).decode()
    query = urllib.parse.urlencode({**params, "scope": f"repository:{repository}:pull"})
    try:
        with request(f"{realm}?{query}", headers) as resp:
            payload = json.load(resp)
    except urllib.error.HTTPError as exc:
        raise ResolveError(f"token request for {repository}: HTTP {exc.code}") from exc
    except (urllib.error.URLError, OSError) as exc:
        raise ResolveError(f"token request for {repository}: {exc}") from exc
    value = payload.get("token") or payload.get("access_token")
    if not value:
        raise ResolveError(f"token response for {repository} carried no token")
    return value


def auth_header(registry: str, repository: str, username: str, password: str) -> dict:
    token = bearer(registry, repository, username, password)
    return {"Authorization": f"Bearer {token}"} if token else {}


def digest(registry: str, repository: str, version: str, username: str, password: str) -> str:
    headers = {**auth_header(registry, repository, username, password), "Accept": ACCEPT}
    url = f"https://{registry}/v2/{repository}/manifests/{version}"
    try:
        with request(url, headers) as resp:
            header = resp.headers.get("Docker-Content-Digest")
            body = resp.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            raise ResolveError(
                f"{repository}:{version} is not readable with these credentials"
            ) from exc
        if exc.code == 404:
            raise ResolveError(f"{repository}:{version} does not exist in {registry}") from exc
        raise ResolveError(f"{repository}:{version}: HTTP {exc.code}") from exc
    except (urllib.error.URLError, OSError) as exc:
        raise ResolveError(f"{repository}:{version}: {exc}") from exc

    if header:
        return header.strip()
    # Registries normally send Docker-Content-Digest. If one omits it, hash the manifest we
    # already read; every registry in use hashes with sha256.
    return "sha256:" + hashlib.sha256(body).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--registry", required=True)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--prefix", default="coder-images")
    parser.add_argument("--username", default=os.environ.get("REGISTRY_USERNAME", ""))
    parser.add_argument("--password", default=os.environ.get("REGISTRY_PASSWORD", ""))
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    try:
        refs = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        print(f"base-digest: stdin was not JSON: {exc}", file=sys.stderr)
        return 2
    if not isinstance(refs, list):
        print('base-digest: stdin must be a JSON array, e.g. ["base:2.0.0"]', file=sys.stderr)
        return 2

    resolved: dict[str, str] = {}
    errors: list[str] = []
    for ref in dict.fromkeys(refs):
        image, sep, version = ref.rpartition(":")
        if not sep or not image or not version:
            errors.append(f"base-digest: {ref!r} is not an image:version reference")
            continue
        repository = f"{args.owner}/{args.prefix}-{image}"
        try:
            resolved[ref] = digest(registry=args.registry, repository=repository, version=version,
                                   username=args.username, password=args.password)
            if not args.quiet:
                print(f"resolved {ref} -> {resolved[ref]}", file=sys.stderr)
        except ResolveError as exc:
            errors.append(str(exc))

    json.dump(resolved, sys.stdout, sort_keys=True)
    print(file=sys.stdout)
    for problem in errors:
        print(f"::error::{problem}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
