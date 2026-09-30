#!/usr/bin/env python3
"""Decide whether one release may be cut, from the registry's tag list.

Usage:
  plan-release.py --registry R --owner O decision <image> <version> [--source-tag src-<key>]
  plan-release.py --registry R --owner O next <image>
  plan-release.py --registry R --owner O floating <image> <version>

`decision` prints {"ok", "code", "message"} and exits 0 only when the release may go ahead.
Codes: ok, unknown_image, bad_version, already_published, below_minimum, not_built, and
probe_error when the registry could not answer (never treat that as a yes: re-pushing a tag
would overwrite an image others pin by digest). --tags-file replaces the registry with a list
of tags, one per line, for tests or an airgapped host.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
import urllib.parse

# Every image's version line starts here; the 1.x tags in ghcr.io are the retired repo-wide line.
MIN_RELEASE = "2.0.0"
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
# A release candidate, X.Y.Z-rc.N: accepted by decide(), never counted as a release.
CANDIDATE_RE = re.compile(r"^\d+\.\d+\.\d+-rc\.\d+$")
HERE = os.path.dirname(os.path.abspath(__file__))


class ReleaseError(Exception):
    pass


def version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def published_versions(tags: list[str]) -> list[str]:
    """Only X.Y.Z tags: latest, main-<sha>, src-<key>, 2.1 and 2 are not releases."""
    return sorted((t for t in tags if SEMVER_RE.match(t)), key=version_key)


def suggest_next(tags: list[str]) -> dict:
    current = [v for v in published_versions(tags) if version_key(v) >= version_key(MIN_RELEASE)]
    if not current:
        return {"highest": "", "next": [MIN_RELEASE], "note": f"no 2.x release yet; next: {MIN_RELEASE}"}
    top = current[-1]
    major, minor, patch = version_key(top)
    nxt = [f"{major}.{minor}.{patch + 1}", f"{major}.{minor + 1}.0", f"{major + 1}.0.0"]
    return {"highest": top, "next": nxt, "note": f"latest release: {top}; next: {' / '.join(nxt)}"}


def floating_tags(version: str, tags: list[str]) -> list[str]:
    """The floating tags a release of `version` should move: X.Y, X and latest.

    Each moves only when this release is the highest version it covers, so releasing a fix for an
    older line (2.0.1 after 2.1.0) moves 2.0 and nothing else. `latest` is the highest version.
    """
    versions = set(published_versions(tags)) | {version}
    major, minor, _ = version_key(version)
    moves = []
    if version == max((v for v in versions if version_key(v)[:2] == (major, minor)), key=version_key):
        moves.append(f"{major}.{minor}")
    if version == max((v for v in versions if version_key(v)[0] == major), key=version_key):
        moves.append(f"{major}")
    if version == max(versions, key=version_key):
        moves.append("latest")
    return moves


def decide(image: str, version: str, images: list[str], tags: list[str],
           source_tag: str = "") -> dict:
    def refuse(code: str, message: str) -> dict:
        return {"ok": False, "code": code, "message": message}

    if image not in images:
        return refuse("unknown_image", f"unknown image {image!r}; known: {', '.join(images)}")
    if not (SEMVER_RE.match(version or "") or CANDIDATE_RE.match(version or "")):
        return refuse("bad_version", f"version must be X.Y.Z or X.Y.Z-rc.N (got: {version})")
    if version in tags:
        return refuse("already_published",
                      f"{image}:{version} is already published; re-releasing it would overwrite "
                      f"an image others may pin by digest. Use a new version.")
    if version_key(version.split("-")[0]) < version_key(MIN_RELEASE):
        return refuse("below_minimum", f"releases start at {MIN_RELEASE}; got {image} {version}")
    if source_tag and source_tag not in tags:
        return refuse("not_built",
                      f"{image}:{source_tag} does not exist yet: main has not published {image} "
                      f"as it is at this commit. Wait for main's build to finish, then release.")
    return {"ok": True, "code": "ok", "message": f"{image} {version} may be released"}


def read_tags(registry: str, repository: str, username: str, password: str) -> list[str]:
    """Every tag of one repository, following the registry's Link paging.

    A repository that was never pushed answers 404 (NAME_UNKNOWN): it has no tags, which is the
    normal state before an image's first build in a registry, not a failure to answer.
    """
    import urllib.error

    spec = importlib.util.spec_from_file_location("bd", os.path.join(HERE, "base-digest.py"))
    bd = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bd)
    headers = bd.auth_header(registry, repository, username, password)
    tags: list[str] = []
    url = f"https://{registry}/v2/{repository}/tags/list?n=1000"
    while url:
        try:
            with bd.request(url, headers) as resp:
                tags += json.load(resp).get("tags") or []
                link = resp.headers.get("Link", "")
        except urllib.error.HTTPError as exc:
            if exc.code == 404 and not tags:
                return []
            raise ReleaseError(f"{registry}/{repository}: tags/list answered HTTP {exc.code}") from exc
        match = re.match(r'\s*<([^>]+)>\s*;\s*rel="?next"?', link)
        url = urllib.parse.urljoin(f"https://{registry}/", match.group(1)) if match else ""
    return tags


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--registry", required=True)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--prefix", default="coder-images")
    # Credentials come from the environment, never the command line, where `ps` would show them.
    parser.add_argument("--username", default=os.environ.get("REGISTRY_USERNAME", ""))
    parser.add_argument("--password", default=os.environ.get("REGISTRY_PASSWORD", ""))
    parser.add_argument("--tags-file", default=os.environ.get("RELEASE_TAGS_FILE") or None)
    sub = parser.add_subparsers(dest="command", required=True)
    p_next = sub.add_parser("next")
    p_next.add_argument("image")
    p_decide = sub.add_parser("decision")
    p_decide.add_argument("image")
    p_decide.add_argument("version")
    p_decide.add_argument("--source-tag", default="")
    p_float = sub.add_parser("floating")
    p_float.add_argument("image")
    p_float.add_argument("version")
    args = parser.parse_args(argv)

    try:
        graph = subprocess.run([sys.executable, os.path.join(HERE, "ci-graph.py"), "images"],
                               capture_output=True, text=True)
        if graph.returncode != 0:
            raise ReleaseError(f"ci-graph.py images: {graph.stderr.strip()}")
        images = json.loads(graph.stdout)
        if args.tags_file:
            with open(args.tags_file, encoding="utf-8") as handle:
                tags = [line.strip() for line in handle if line.strip()]
        else:
            tags = read_tags(args.registry, f"{args.owner}/{args.prefix}-{args.image}",
                             args.username, args.password)
    except Exception as exc:  # noqa: BLE001 - any failure to read the registry is probe_error
        print(json.dumps({"ok": False, "code": "probe_error", "message": f"{type(exc).__name__}: {exc}"}))
        return 3

    if args.command == "next":
        print(json.dumps(suggest_next(tags)))
        return 0
    if args.command == "floating":
        if not SEMVER_RE.match(args.version):
            print(json.dumps({"ok": False, "code": "bad_version", "message": f"not X.Y.Z: {args.version}"}))
            return 1
        print(json.dumps(floating_tags(args.version, tags)))
        return 0
    verdict = decide(args.image, args.version, images, tags, args.source_tag)
    print(json.dumps(verdict))
    return 0 if verdict["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
