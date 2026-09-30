#!/usr/bin/env python3
"""Derive the CI build plan from .ci/graph.json (see README, "The image graph").

Usage:
  ci-graph.py images                     every image name, as JSON
  ci-graph.py check                      assert the graph matches the tree
  ci-graph.py pins                       every <base>:<pinned version>, as JSON
  ci-graph.py key <image> [--rev REV]    content key of an image's build inputs
  ci-graph.py plan --registry <host> --event <push|pull_request|workflow_dispatch|tag> ...
                                         the build plan, as JSON

A branch event builds the images whose inputs changed. A release tag (<image>-vX.Y.Z) builds
nothing: it names the image, version and content key for scripts/promote.sh. A release-candidate
tag (<image>-vX.Y.Z-rc.N) builds that one image at the tagged commit, which may be any branch,
and publishes it only as X.Y.Z-rc.N.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys

IMAGE_KEYS = {"from", "description", "apt_upgrade", "extra_paths"}
BASE_VERSION_RE = re.compile(r"^\s*ARG\s+BASE_VERSION=(\S+)\s*$", re.MULTILINE)
BASE_NAME_RE = re.compile(r"^\s*ARG\s+BASE_NAME=(\S+)\s*$", re.MULTILINE)
BASE_REF_RE = re.compile(r"^\s*ARG\s+BASE_REF=\$\{BASE_NAME\}:\$\{BASE_VERSION\}\s*$", re.MULTILINE)
FROM_REF_RE = re.compile(r"^\s*FROM\s+\$\{BASE_REF\}\s*$", re.MULTILINE)
APT_UPGRADE_RE = re.compile(r"\bapt(?:-get)?\s+(?:-\S+\s+)*upgrade\b")
APT_UPGRADE_GUARD_RE = re.compile(r'"\$APT_UPGRADE"\s*=\s*"?true')
# Build args that change on every commit. Declared before a RUN, COPY or ADD they become part of
# its cache key, so the image rebuilds from that step on every commit.
PROVENANCE_ARG_RE = re.compile(r"^\s*ARG\s+(?:VERSION|GIT_SHA|BUILD_CREATED)\b", re.MULTILINE)
BUILD_STEP_RE = re.compile(r"^\s*(?:RUN|COPY|ADD)\b", re.MULTILINE)
# A workspace mounts its persistent home volume over /home/coder, and a Kubernetes volume is not
# seeded from the image: anything a build puts there is hidden. Only these runtime defaults, which
# point at user data rather than image content, may name the home directory.
HOME = "/home/coder"
HOME_ALLOWED = {"GOPATH": "/home/coder/go", "GOBIN": "/home/coder/go/bin"}
HOME_REF_RE = re.compile(r"/home/coder\b|\$\{?HOME\b|(?<![\w/.~-])~(?=/|\s|$|[\"'])")
ENV_REF_RE = re.compile(r"\$\{?(\w+)\}?")
# Commands that write under $HOME by default: harmless as root (/root), hidden as coder.
HOME_WRITER_RE = re.compile(
    r"\bpip3?\s+install\b[^&;|]*\s--user\b|\bpipx\s+install\b|\buv\s+tool\s+install\b"
    r"|\bnpm\s+(?:i|install|add)\b[^&;|]*\s(?:-g|--global)\b|\bgit\s+config\s+--global\b")
GO_WRITER_RE = re.compile(r"\bgo\s+(?:install|get|build|mod\s+download)\b")
TAG_RE = re.compile(r"^(?P<image>.+)-v(?P<version>\d+\.\d+\.\d+(?P<rc>-rc\.\d+)?)$")


class GraphError(Exception):
    pass


def git(root: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=root, capture_output=True)


def load_graph(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, ValueError) as exc:
        raise GraphError(f"cannot read {path}: {exc}") from exc
    images = raw.get("images") or {}
    if not images:
        raise GraphError(f"{path}: no images defined")
    for name, spec in images.items():
        unknown = set(spec) - IMAGE_KEYS
        if unknown:
            raise GraphError(f"{path}: images.{name} has unknown keys {sorted(unknown)}")
        spec["dockerfile"] = f"images/{name}/Dockerfile"
        spec["paths"] = [f"images/{name}/", f"src/{name}/", *spec.get("extra_paths", [])]
    return {"defaults": raw.get("defaults") or {}, "images": images}


def matches(path: str, pattern: str) -> bool:
    """A trailing slash matches a directory prefix; anything else is a path or a glob."""
    if pattern.endswith("/"):
        return path.startswith(pattern)
    return path == pattern or fnmatch.fnmatch(path, pattern)


def owners(graph: dict, path: str) -> list[str]:
    return [n for n, s in graph["images"].items() if any(matches(path, p) for p in s["paths"])]


def is_consumer(graph: dict, path: str) -> bool:
    return any(matches(path, p) for p in graph["defaults"].get("consumers", []))


def read_dockerfile(root: str, spec: dict) -> str:
    try:
        with open(os.path.join(root, spec["dockerfile"]), encoding="utf-8") as handle:
            return handle.read()
    except OSError:
        return ""


def base_version(root: str, spec: dict) -> str:
    """The base version a dependent pins with ARG BASE_VERSION; empty for a standalone image."""
    if not spec.get("from"):
        return ""
    match = BASE_VERSION_RE.search(read_dockerfile(root, spec))
    return match.group(1) if match else ""


def inputs_key(root: str, graph: dict, name: str, rev: str = "HEAD") -> str:
    """Content key of everything that decides an image's content.

    The same paths that rebuild the image: its own paths and the catch-alls. Main builds
    publish src-<key>, and a release promotes that tag, so identical inputs give the same key
    whichever commit built them.
    """
    paths = graph["images"][name]["paths"] + graph["defaults"].get("catch_all", [])
    out = git(root, "ls-tree", "-r", "-z", rev, "--", *sorted(set(paths)))
    if out.returncode != 0:
        raise GraphError(f"cannot read the tree at {rev!r}: {out.stderr.decode().strip()}")
    return hashlib.sha256(out.stdout).hexdigest()[:16]


def parents(images: dict, name: str) -> list[str]:
    """The images `name` is built on, nearest first (golang, then base, for app)."""
    chain: list[str] = []
    base = images[name].get("from")
    while base in images and base not in chain:
        chain.append(base)
        base = images[base].get("from")
    return chain


def instructions(text: str) -> list[tuple[int, str, str]]:
    """(line, KEYWORD, arguments) per Dockerfile instruction, continuations joined, comments dropped."""
    result: list[tuple[int, str, str]] = []
    start, parts = 0, []
    for number, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("#") or (not parts and not line.strip()):
            continue
        if not parts:
            start = number
        parts.append(line.rstrip())
        if parts[-1].endswith("\\"):
            parts[-1] = parts[-1][:-1]
            continue
        keyword, _, rest = " ".join(parts).strip().partition(" ")
        result.append((start, keyword.upper(), rest.strip()))
        parts = []
    return result


def env_assignments(rest: str) -> list[tuple[str, str]]:
    """ENV K=V K2=V2, or the legacy ENV K V."""
    words = shlex.split(rest)
    if words and "=" not in words[0]:
        return [(words[0], " ".join(words[1:]))]
    return [tuple(w.split("=", 1)) for w in words if "=" in w]


def home_problems(root: str, graph: dict, name: str) -> tuple[list[str], dict[str, str]]:
    """Build steps that put image content under /home/coder, and the image's final ENV.

    A dependent starts from its parent's final ENV, so app sees golang's GOPATH.
    """
    spec = graph["images"][name]
    chain = parents(graph["images"], name)
    # A broken from chain is reported by check; inherit nothing rather than recurse forever.
    inherited = home_problems(root, graph, chain[0])[1] if chain and name not in chain else {}
    problems: list[str] = []
    env, user = {}, "root"

    def resolve(value: str) -> str:
        return ENV_REF_RE.sub(lambda m: env.get(m.group(1), m.group(0)), value)

    for number, keyword, rest in instructions(read_dockerfile(root, spec)):
        where = f"{name}: {spec['dockerfile']}:{number}: {keyword}"
        if keyword == "FROM":
            env = dict(inherited) if "${BASE_REF}" in rest else {}
            inherited, user = {}, "root"
        elif keyword == "USER":
            user = rest.split(":")[0]
        elif keyword == "ENV":
            for key, value in env_assignments(rest):
                value = resolve(value)
                env[key] = value
                if key == "PATH":
                    bad = [p for p in value.split(":")
                           if HOME_REF_RE.search(p) and p not in HOME_ALLOWED.values()]
                else:
                    bad = [value] if HOME_REF_RE.search(value) and HOME_ALLOWED.get(key) != value else []
                if bad:
                    problems.append(f"{where} {key} points into {HOME}, which a workspace's home "
                                    f"volume hides: {', '.join(bad)} (runtime defaults allowed: "
                                    f"{', '.join(sorted(HOME_ALLOWED))})")
        elif keyword in ("RUN", "COPY", "ADD", "WORKDIR"):
            text = resolve(rest)
            if HOME_REF_RE.search(text):
                problems.append(f"{where} writes or reads under {HOME}, which a workspace's home "
                                f"volume hides; install under /opt or /usr/local instead")
            elif keyword == "RUN" and user not in ("root", "0") and HOME_WRITER_RE.search(text):
                problems.append(f"{where} as {user} installs or configures under {HOME}, which a "
                                f"workspace's home volume hides; use /opt, /usr/local or /etc")
            elif keyword == "RUN" and GO_WRITER_RE.search(text) and any(
                    HOME_REF_RE.search(env.get(k, "")) and f"{k}=" not in text
                    for k in ("GOPATH", "GOBIN")):
                problems.append(f"{where} runs go with GOPATH or GOBIN under {HOME}; set "
                                f"GOBIN=/usr/local/bin and a temporary GOPATH in that RUN")
    return problems, env


def check(root: str, graph: dict) -> list[str]:
    """Every rule that keeps the graph, the Dockerfiles and the tree in agreement."""
    problems: list[str] = []
    images = graph["images"]
    for name in sorted(os.listdir(os.path.join(root, "images"))):
        if os.path.isfile(os.path.join(root, "images", name, "Dockerfile")) and name not in images:
            problems.append(f"images/{name}/Dockerfile exists but {name} is not in the graph")

    for name, spec in images.items():
        text = read_dockerfile(root, spec)
        if not text:
            problems.append(f"{name}: cannot read {spec['dockerfile']}")
            continue
        code = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))
        gated = "ARG APT_UPGRADE=false" in code and APT_UPGRADE_GUARD_RE.search(code)
        if APT_UPGRADE_RE.search(code) and not gated:
            problems.append(f"{name}: apt upgrade must sit behind ARG APT_UPGRADE=false")
        if bool(spec.get("apt_upgrade")) != bool(gated):
            problems.append(f"{name}: apt_upgrade in the graph must match a gated apt upgrade")
        provenance = PROVENANCE_ARG_RE.search(code)
        if provenance and BUILD_STEP_RE.search(code, provenance.end()):
            problems.append(f"{name}: declare ARG VERSION/GIT_SHA/BUILD_CREATED after the last "
                            f"RUN/COPY/ADD, or every commit invalidates the build cache")

        problems.extend(home_problems(root, graph, name)[0])

        base = spec.get("from")
        if not base:
            continue
        if base not in images:
            problems.append(f"{name}: from {base!r} must name an image in the graph")
        elif name in parents(images, name):
            problems.append(f"{name}: its from chain leads back to itself")
        base_name = BASE_NAME_RE.search(code)
        if not base_name or not base_name.group(1).endswith(f"coder-images-{base}"):
            problems.append(f"{name}: needs ARG BASE_NAME=<registry>/<owner>/coder-images-{base}")
        if base_version(root, spec) in ("", "latest"):
            problems.append(f"{name}: needs ARG BASE_VERSION=<version>, not latest")
        if not BASE_REF_RE.search(code) or not FROM_REF_RE.search(code):
            problems.append(f"{name}: needs ARG BASE_REF=${{BASE_NAME}}:${{BASE_VERSION}} and FROM ${{BASE_REF}}")

    catch_all = set(graph["defaults"].get("catch_all", []))
    tracked = git(root, "ls-files", "-z").stdout.decode().split("\0")
    for path in filter(None, tracked):
        if not owners(graph, path) and not is_consumer(graph, path) and path not in catch_all:
            problems.append(
                f"{path}: no image owns it and it is not a consumer, so changing it would "
                f"rebuild every image. Classify it in .ci/graph.json"
            )
    return problems


def changed_paths(root: str, ref: str, event: str) -> list[str]:
    """Files that differ between ref and HEAD.

    A pull request compares against the merge base (three dots), so changes on the target branch
    are not attributed to it. A push compares the two trees directly (two dots): after a
    force-push that reverts a change, the merge base would hide the reverted files.
    """
    specs = (f"{ref}...HEAD", f"{ref}..HEAD") if event == "pull_request" else (f"{ref}..HEAD",)
    for spec in specs:
        out = git(root, "diff", "--name-only", "--no-renames", "-z", spec)
        if out.returncode == 0:
            return [p for p in out.stdout.decode().split("\0") if p]
    raise GraphError(f"cannot diff HEAD against {ref!r} (is the fetch shallow?)")


def selected(graph: dict, args: argparse.Namespace) -> dict[str, str]:
    """Images this branch event builds, with the reason for each."""
    images = graph["images"]
    if args.images:
        requested = [n.strip() for n in args.images.split(",") if n.strip()]
        unknown = [n for n in requested if n not in images]
        if unknown:
            raise GraphError(f"unknown images: {', '.join(unknown)}")
        return {n: "dispatch" for n in requested}
    if args.all:
        return {n: "all" for n in images}

    paths = list(args.changed_file or [])
    if args.changed_base:
        paths += changed_paths(args.root, args.changed_base, args.event)
    reasons: dict[str, str] = {}
    for path in paths:
        hit = owners(graph, path)
        if hit:
            for name in hit:
                reasons.setdefault(name, f"changed:{path}")
        elif not is_consumer(graph, path):
            for name in images:
                reasons.setdefault(name, f"shared:{path}")
    # A package refresh is asked for by the upgrade_base input alone, so it selects every image
    # that can refresh, whatever else changed.
    if args.upgrade_base == "true":
        for name, spec in images.items():
            if spec.get("apt_upgrade"):
                reasons.setdefault(name, "upgrade_base")
    return reasons


def publish_gate(defaults: dict, repository: str) -> tuple[bool, str]:
    """May this run publish? Only runs of the repositories in publish_repositories may: a fork on
    GitHub still reports ghcr.io, so the repository is what tells it apart. Where images go is
    the workflow's choice (ghcr.io, or the REGISTRY repository variable), so it is not listed
    here. An unsupplied repository is unknown, not denied."""
    repositories = [r.lower() for r in defaults.get("publish_repositories", [])]
    if repository and repository.lower() not in repositories:
        return False, f"repository {repository} is not in publish_repositories"
    return True, "the repository may publish"


def plan(graph: dict, args: argparse.Namespace) -> dict:
    allowed, reason = publish_gate(graph["defaults"], args.repository)
    payload = {
        "build": [], "base": None, "standalone": [], "dependent": [], "digest_refs": [],
        "count": 0, "empty": True, "reasons": {}, "release": None,
        "publish": {"allowed": allowed, "reason": reason,
                    "registry": args.registry, "repository": args.repository},
    }

    if args.event == "tag":
        name = args.ref.rpartition("/")[2]
        match = TAG_RE.match(name)
        if not match:
            raise GraphError(f"tag {name!r} must look like <image>-vX.Y.Z[-rc.N], e.g. cortex-v2.0.0")
        image = match.group("image")
        if image not in graph["images"]:
            raise GraphError(f"tag {name!r} names unknown image {image!r}")
        if match.group("rc"):
            # A candidate has no main build to promote, so it is built from the tagged commit.
            return plan_build(graph, args, payload, {image: f"rc:{name}"}, "rc",
                              match.group("version"), allowed)
        payload["release"] = {
            "image": image,
            "version": match.group("version"),
            "key": inputs_key(args.root, graph, image),
            "publish": "true" if allowed else "false",
        }
        return payload

    # Only the default branch publishes: its builds are what a release later promotes.
    tag_source = "branch" if args.ref_name == args.default_branch else "skip"
    return plan_build(graph, args, payload, selected(graph, args), tag_source, "", allowed)


def plan_build(graph: dict, args: argparse.Namespace, payload: dict, reasons: dict[str, str],
               tag_source: str, version: str, allowed: bool) -> dict:
    build = []
    for name, spec in graph["images"].items():
        if name not in reasons:
            continue
        capable = bool(spec.get("apt_upgrade"))
        refresh = capable and args.upgrade_base == "true"
        build.append({
            "name": name,
            "dockerfile": spec["dockerfile"],
            "description": spec.get("description", ""),
            # "" = the image declares no APT_UPGRADE arg, so the action must not override it.
            "apt_upgrade_arg": ("true" if refresh else "false") if capable else "",
            "from": spec.get("from", ""),
            "base_version": base_version(args.root, spec),
            "inputs_key": inputs_key(args.root, graph, name),
            "tag_source": tag_source,
            "version": version,
            "branch": args.ref_name,
            "publish": "true" if allowed and tag_source != "skip" else "false",
        })

    payload.update(
        build=build,
        # base gets its own job so its failure is visible on its own.
        base=next((e for e in build if e["name"] == "base"), None),
        standalone=[e for e in build if not e["from"] and e["name"] != "base"],
        dependent=[e for e in build if e["from"]],
        digest_refs=sorted({f"{e['from']}:{e['base_version']}" for e in build if e["from"]}),
        count=len(build),
        empty=not build,
        reasons=reasons,
    )
    return payload


def write_summary(payload: dict) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    lines = ["### Build plan", ""]
    release = payload["release"]
    if release:
        lines.append(f"Release: promote `{release['image']}:src-{release['key']}` "
                     f"to `{release['version']}`. Nothing is built.")
    elif payload["empty"]:
        lines.append("No image content changed, so nothing is built or published.")
    else:
        lines += ["| Image | Base pin | Source key | Publish | Why |", "|---|---|---|---|---|"]
        for e in payload["build"]:
            base = f"`{e['from']}:{e['base_version']}`" if e["from"] else "—"
            lines.append(f"| `{e['name']}` | {base} | `src-{e['inputs_key']}` | {e['publish']} "
                         f"| {payload['reasons'][e['name']]} |")
    gate = payload["publish"]
    lines += ["", f"**Publish gate:** {'open' if gate['allowed'] else 'closed'} — {gate['reason']}"]
    with open(path, "a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=None)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("images")
    sub.add_parser("check")
    sub.add_parser("pins")
    p_key = sub.add_parser("key")
    p_key.add_argument("image")
    p_key.add_argument("--rev", default="HEAD")
    p_plan = sub.add_parser("plan")
    p_plan.add_argument("--event", default="push",
                        choices=("push", "pull_request", "workflow_dispatch", "tag"))
    p_plan.add_argument("--ref", default="")
    p_plan.add_argument("--ref-name", default="")
    p_plan.add_argument("--default-branch", default="main")
    p_plan.add_argument("--registry", required=True)
    p_plan.add_argument("--repository", default="")
    p_plan.add_argument("--changed-base")
    p_plan.add_argument("--changed-file", action="append")
    p_plan.add_argument("--images")
    p_plan.add_argument("--all", action="store_true")
    p_plan.add_argument("--upgrade-base", choices=("true", "false"), default="false")
    p_plan.add_argument("--summary", action="store_true")
    args = parser.parse_args(argv)

    if args.root is None:
        here = os.path.dirname(os.path.abspath(__file__))
        top = git(here, "rev-parse", "--show-toplevel")
        args.root = top.stdout.decode().strip() if top.returncode == 0 else os.path.dirname(here)

    try:
        graph = load_graph(os.path.join(args.root, ".ci", "graph.json"))
        images = graph["images"]
        if args.command == "images":
            print(json.dumps(list(images)))
        elif args.command == "check":
            problems = check(args.root, graph)
            for problem in problems:
                print(f"::error::{problem}", file=sys.stderr)
            if problems:
                return 1
            print(f"graph ok: {len(images)} images")
        elif args.command == "pins":
            print(json.dumps(sorted({f"{s['from']}:{base_version(args.root, s)}"
                                     for s in images.values() if s.get("from")})))
        elif args.command == "key":
            if args.image not in images:
                raise GraphError(f"unknown image {args.image!r}")
            print(inputs_key(args.root, graph, args.image, args.rev))
        else:
            payload = plan(graph, args)
            print(json.dumps(payload, separators=(",", ":"), sort_keys=True))
            if args.summary:
                write_summary(payload)
    except GraphError as exc:
        print(f"ci-graph: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
