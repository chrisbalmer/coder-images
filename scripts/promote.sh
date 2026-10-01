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
# floating): a fix for an older line never moves latest. The per-platform manifests are
# unchanged; the new index only adds the version annotation, which is why the version tag's
# digest differs from src-<key>'s.
#
# A version tag never moves. A re-run of a release (validate-release-tag.sh lets attempt 2 find
# its version published) may meet a src-<key> that has moved since, for example after an
# upgrade_base rebuild under the same key. If <version> already exists, its per-platform
# manifests are compared with src-<key>'s: the same, and only the floating tags are re-applied;
# different, and the release is refused.
#
# Needs `docker buildx` (0.12+ for --annotation), `jq`, a registry login, and
# REGISTRY_USERNAME / REGISTRY_PASSWORD in the environment to read the published tags.

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

# The per-platform manifests a reference names, sorted: an index's children, or the one manifest.
platform_manifests() {
    local raw
    raw=$(docker buildx imagetools inspect --raw "$1") || return 1
    if jq -e '.manifests' <<<"$raw" > /dev/null; then
        jq -r '[.manifests[].digest] | sort | .[]' <<<"$raw"
    else
        docker buildx imagetools inspect "$1" --format '{{.Manifest.Digest}}'
    fi
}

# PREFIX is <registry>/<owner>/<name>; the tag list is read before anything is tagged.
REST=${PREFIX#*/}
PROBE=(--registry "${PREFIX%%/*}" --owner "${REST%/*}" --prefix "${REST##*/}")
DECISION=$(python3 "$(dirname "$0")/plan-release.py" "${PROBE[@]}" decision "$IMAGE" "$VERSION" || true)
case "$(jq -r '.code // empty' <<<"$DECISION" 2> /dev/null || true)" in
    already_published) PUBLISHED=true ;;
    probe_error|'')
        echo "::error::could not read ${REPO}'s tags to check ${VERSION}: ${DECISION:-}"
        exit 1 ;;
    *) PUBLISHED=false ;;
esac
FLOATING=$(python3 "$(dirname "$0")/plan-release.py" "${PROBE[@]}" floating "$IMAGE" "$VERSION") \
    || { echo "::error::could not read ${REPO}'s tags to decide the floating tags: ${FLOATING:-}"; exit 1; }
FLOAT=()
while read -r tag; do FLOAT+=("$tag"); done < <(jq -r '.[]' <<<"$FLOATING")

if [ "$PUBLISHED" = true ]; then
    HAVE=$(platform_manifests "${REPO}:${VERSION}") \
        || { echo "::error::${REPO}:${VERSION} is listed but could not be read"; exit 1; }
    WANT=$(platform_manifests "$SRC") || { echo "::error::could not read ${SRC}"; exit 1; }
    if [ "$HAVE" != "$WANT" ]; then
        echo "::error::${REPO}:${VERSION} is already published with different images than ${SRC}."
        echo "::error::A version tag never moves: release a new version instead."
        exit 1
    fi
    echo "${REPO}:${VERSION} is already published from ${SRC}; re-applying only its floating tags"
    TAGS=("${FLOAT[@]+"${FLOAT[@]}"}")
    if [ "${#TAGS[@]}" -gt 0 ]; then
        TAG_ARGS=()
        for tag in "${TAGS[@]}"; do TAG_ARGS+=(--tag "${REPO}:${tag}"); done
        # One source and no annotation: the floating tags get the version's own index.
        docker buildx imagetools create "${TAG_ARGS[@]}" "${REPO}:${VERSION}"
    fi
else
    TAGS=("${VERSION}" "${FLOAT[@]+"${FLOAT[@]}"}")
    TAG_ARGS=()
    for tag in "${TAGS[@]}"; do TAG_ARGS+=(--tag "${REPO}:${tag}"); done
    docker buildx imagetools create \
        --annotation "index:org.opencontainers.image.version=${VERSION}" \
        "${TAG_ARGS[@]}" \
        "$SRC"
fi

DIGEST=$(docker buildx imagetools inspect "${REPO}:${VERSION}" --format '{{.Manifest.Digest}}')
echo "Released ${REPO}:${VERSION} @ ${DIGEST} (from ${SRC})"
if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
    {
        printf '### %s %s\n\n' "$REPO" "$VERSION"
        printf -- '- **Digest:** `%s`\n' "$DIGEST"
        printf -- '- **Promoted from:** `%s`\n' "$SRC"
        printf -- '- **Tags:** `%s`\n' "${TAGS[*]:-none moved}"
    } >> "$GITHUB_STEP_SUMMARY"
fi
