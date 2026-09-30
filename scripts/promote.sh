#!/usr/bin/env bash
# Release one image by promoting the image main already built: no rebuild.
#
# Usage: scripts/promote.sh <image-prefix> <image> <version> <inputs-key>
#        scripts/promote.sh ghcr.io/chrisbalmer/coder-images cortex 2.1.0 c7e205528e123fca
#
# Every published main build carries src-<key>, where the key hashes that image's build inputs
# (scripts/ci-graph.py key). The release job computes the key at the tagged commit and points
# the version tag at that exact image, so a release ships what main built and tested. X.Y, X and
# latest move too, but only where this is the highest version they cover (plan-release.py
# floating): a fix for an older line never moves latest. The per-platform manifests are unchanged; the new index only adds the version
# annotation, which is why the version tag's digest differs from src-<key>'s.
#
# Needs `docker buildx` (0.12+ for --annotation), a registry login, and REGISTRY_USERNAME /
# REGISTRY_PASSWORD in the environment to read the published tags.

set -euo pipefail

PREFIX=${1:?usage: promote.sh <image-prefix> <image> <version> <inputs-key>}
IMAGE=${2:?usage: promote.sh <image-prefix> <image> <version> <inputs-key>}
VERSION=${3:?usage: promote.sh <image-prefix> <image> <version> <inputs-key>}
KEY=${4:?usage: promote.sh <image-prefix> <image> <version> <inputs-key>}

REPO="${PREFIX}-${IMAGE}"
SRC="${REPO}:src-${KEY}"

if ! docker buildx imagetools inspect "$SRC" > /dev/null 2>&1; then
    echo "::error::${SRC} does not exist: main has not published ${IMAGE} as it is at this commit."
    echo "::error::Wait for main's build to finish (or run the workflow on main with images=${IMAGE}), then re-run this job."
    exit 1
fi

# PREFIX is <registry>/<owner>/<name>; the tag list is read before anything is tagged.
REST=${PREFIX#*/}
FLOATING=$(python3 "$(dirname "$0")/plan-release.py" --registry "${PREFIX%%/*}" --owner "${REST%/*}" \
    --prefix "${REST##*/}" floating "$IMAGE" "$VERSION") \
    || { echo "::error::could not read ${REPO}'s tags to decide the floating tags: ${FLOATING:-}"; exit 1; }
TAGS=("${VERSION}")
while read -r tag; do TAGS+=("$tag"); done < <(jq -r '.[]' <<<"$FLOATING")
TAG_ARGS=()
for tag in "${TAGS[@]}"; do TAG_ARGS+=(--tag "${REPO}:${tag}"); done

docker buildx imagetools create \
    --annotation "index:org.opencontainers.image.version=${VERSION}" \
    "${TAG_ARGS[@]}" \
    "$SRC"

DIGEST=$(docker buildx imagetools inspect "${REPO}:${VERSION}" --format '{{.Manifest.Digest}}')
echo "Released ${REPO}:${VERSION} @ ${DIGEST} (from ${SRC})"
if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
    {
        printf '### %s %s\n\n' "$REPO" "$VERSION"
        printf -- '- **Digest:** `%s`\n' "$DIGEST"
        printf -- '- **Promoted from:** `%s`\n' "$SRC"
        printf -- '- **Tags:** `%s`\n' "${TAGS[*]}"
    } >> "$GITHUB_STEP_SUMMARY"
fi
