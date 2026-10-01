#!/usr/bin/env bash
# Release ONE image by pushing a per-image tag: cortex-v2.0.0, base-v2.0.0, ...
#
# Nothing is rebuilt: CI promotes the image main already built from this commit's inputs
# (src-<key>, see scripts/promote.sh) to <version>, <major>.<minor>, <major> and latest.
#
# Usage: scripts/release.sh <image> <version> [--remote <name>] [--dry-run]
#
# Refuses unless: HEAD is the tip of the remote's main and the tree is clean; main has published
# the image as it is at HEAD; the version is X.Y.Z, at least 2.0.0 and not already published.
#
# Environment:
#   REGISTRY / IMAGE_OWNER / NAME_PREFIX   where to look (default ghcr.io/<owner>/coder-images,
#                                          the owner taken from the remote's URL); the same
#                                          names the publish workflow uses
#   REGISTRY_USERNAME / REGISTRY_PASSWORD               for a private registry
#   RELEASE_TAGS_FILE   read published tags from this file instead of the registry

set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

REGISTRY=${REGISTRY:-ghcr.io}
PREFIX=${NAME_PREFIX:-coder-images}
REMOTE=""
DRY_RUN=false
ARGS=()

usage() { awk 'NR > 1 { if (!/^#/) exit; sub(/^# ?/, ""); print }' "$0"; }
die() { echo "❌ $*" >&2; exit 1; }
# The owner in a remote's URL: git@host:Owner/repo.git, https://host/Owner/repo and
# ssh://git@host:port/Owner/repo.git all give "Owner".
remote_owner() {
    local url
    url=$(git remote get-url "$1" 2> /dev/null) || return 1
    url=${url%/}
    url=${url%.git}
    url=${url%/*}
    url=${url##*[/:]}
    [ -n "$url" ] && printf '%s\n' "$url"
}

while [ $# -gt 0 ]; do
    case "$1" in
        --remote) REMOTE=${2:?--remote needs a name}; shift 2 ;;
        --dry-run) DRY_RUN=true; shift ;;
        -h|--help) usage; exit 0 ;;
        -*) usage >&2; die "unknown option: $1" ;;
        *) ARGS+=("$1"); shift ;;
    esac
done
[ "${#ARGS[@]}" -eq 2 ] || { usage >&2; exit 1; }
IMAGE=${ARGS[0]}
VERSION=${ARGS[1]}
TAG="${IMAGE}-v${VERSION}"
[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || die "version must be X.Y.Z; for a release candidate push a tag by hand: git tag ${IMAGE}-v<X.Y.Z>-rc.<N> && git push <remote> <tag>"

# The tag must point at exactly what main is: the release promotes main's build of it.
[ "$(git branch --show-current)" = main ] || die "releases are cut from main; you are on '$(git branch --show-current)'"
git diff-index --quiet HEAD -- || die "uncommitted changes; commit or stash them first"
if [ -z "$REMOTE" ]; then
    for candidate in github origin; do
        if git remote | grep -qx "$candidate"; then REMOTE=$candidate; break; fi
    done
fi
[ -n "$REMOTE" ] || die "no git remote named github or origin; pass --remote <name>"
OWNER=${IMAGE_OWNER:-$(remote_owner "$REMOTE" || echo chrisbalmer)}
OWNER=$(tr '[:upper:]' '[:lower:]' <<<"$OWNER")  # registry paths are lowercase, as in CI
git fetch -q "$REMOTE" main || die "cannot fetch ${REMOTE}/main"
[ "$(git rev-parse HEAD)" = "$(git rev-parse "${REMOTE}/main")" ] \
    || die "HEAD is not the tip of ${REMOTE}/main; run: git pull --ff-only ${REMOTE} main"
! git rev-parse -q --verify "refs/tags/${TAG}" > /dev/null || die "tag ${TAG} already exists locally"

KEY=$(python3 scripts/ci-graph.py key "$IMAGE" 2> /dev/null) || die "unknown image: $IMAGE"
# plan-release.py reads REGISTRY_USERNAME / REGISTRY_PASSWORD from the environment.
PROBE=(--registry "$REGISTRY" --owner "$OWNER" --prefix "$PREFIX")
if [ -n "${RELEASE_TAGS_FILE:-}" ]; then
    PROBE+=(--tags-file "$RELEASE_TAGS_FILE")
    echo "Reading published tags from ${RELEASE_TAGS_FILE} instead of ${REGISTRY}"
fi
field() { python3 -c 'import json,sys; print(json.load(sys.stdin).get(sys.argv[1], ""))' "$1" 2> /dev/null; }
DECISION=$(python3 scripts/plan-release.py "${PROBE[@]}" decision "$IMAGE" "$VERSION" --source-tag "src-${KEY}" || true)
case "$(field code <<<"$DECISION")" in
    ok) ;;
    probe_error|'') die "could not check ${IMAGE}:${VERSION} against ${REGISTRY}: $(field message <<<"$DECISION")" ;;
    *) die "$(field message <<<"$DECISION")" ;;
esac
echo "Numbering for ${IMAGE}: $(python3 scripts/plan-release.py "${PROBE[@]}" next "$IMAGE" | field note)"

echo "Tag ${TAG} at $(git rev-parse --short HEAD) promotes ${REGISTRY}/${OWNER}/${PREFIX}-${IMAGE}:src-${KEY}"
# The same question promote.sh asks in CI: which floating tags this release heads.
FLOATING=$(python3 scripts/plan-release.py "${PROBE[@]}" floating "$IMAGE" "$VERSION" \
    | python3 -c 'import json,sys; print(", ".join(json.load(sys.stdin)))' 2> /dev/null || true)
echo "  as ${VERSION}${FLOATING:+, and moves ${FLOATING}}"
if [ "$DRY_RUN" = true ]; then
    echo "Dry run. Would run: git tag ${TAG} && git push ${REMOTE} ${TAG}"
    exit 0
fi
git tag "$TAG"
git push "$REMOTE" "$TAG"
echo "✅ Pushed ${TAG}. Verify when CI finishes: scripts/get-digest.sh ${IMAGE} ${VERSION}"
