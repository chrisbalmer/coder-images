#!/usr/bin/env bash
# Refuse a release tag unless it is on main and names an unpublished image version. A release
# candidate (<image>-vX.Y.Z-rc.N) may come from any branch: validating a branch is its purpose.
#
# Usage: validate-release-tag.sh <registry> <owner> <tag-ref> [main-ref]
#
# Environment:
#   REGISTRY_USERNAME / REGISTRY_PASSWORD   credentials for the registry probe
#   RUN_ATTEMPT         the CI run attempt; above 1 the version may already be published
#   RELEASE_TAGS_FILE   consult this tag list instead of the registry (tests, airgapped)
#
# The tagged commit must be *on* main, not its tip: main may legitimately move between the tag
# push and this run. release.sh is the stricter gate that insists on the tip when tagging.
#
# A re-run of the same release run (RUN_ATTEMPT > 1) is allowed to find its version published:
# a release that pushed base and then failed on a dependent must be recoverable. A re-pushed tag
# starts a new run at attempt 1, so it still cannot overwrite a published version.

set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

REGISTRY=${1:?usage: validate-release-tag.sh <registry> <owner> <tag-ref> [main-ref]}
OWNER=${2:?usage: validate-release-tag.sh <registry> <owner> <tag-ref> [main-ref]}
TAG_REF=${3:?usage: validate-release-tag.sh <registry> <owner> <tag-ref> [main-ref]}
MAIN_REF=${4:-origin/main}
PREFIX=${NAME_PREFIX:-coder-images}
TAG=${TAG_REF#refs/tags/}

if [[ ! "$TAG" =~ ^(.+)-v([0-9]+\.[0-9]+\.[0-9]+(-rc\.[0-9]+)?)$ ]]; then
    echo "Release tag must look like <image>-vX.Y.Z or <image>-vX.Y.Z-rc.N (got: $TAG)" >&2
    exit 1
fi
IMAGE=${BASH_REMATCH[1]}
VERSION=${BASH_REMATCH[2]}
CANDIDATE=${BASH_REMATCH[3]}

if [ -z "$CANDIDATE" ]; then
    if ! git rev-parse --verify --quiet "${MAIN_REF}^{commit}" > /dev/null; then
        echo "Cannot verify the release: $MAIN_REF is unavailable." >&2
        exit 1
    fi
    if ! git merge-base --is-ancestor HEAD "$MAIN_REF"; then
        echo "Refusing $TAG: tagged commit $(git rev-parse --short HEAD) is not on $MAIN_REF." >&2
        exit 1
    fi
fi

# plan-release.py reads REGISTRY_USERNAME / REGISTRY_PASSWORD from the environment.
ARGS=(--registry "$REGISTRY" --owner "$OWNER" --prefix "$PREFIX")
if [ -n "${RELEASE_TAGS_FILE:-}" ]; then
    ARGS+=(--tags-file "$RELEASE_TAGS_FILE")
fi

STATUS=0
DECISION=$(python3 scripts/plan-release.py "${ARGS[@]}" decision "$IMAGE" "$VERSION") || STATUS=$?
read_field() {
    python3 -c 'import json,sys; print(json.load(sys.stdin).get(sys.argv[1], ""))' "$1" \
        <<<"$DECISION" 2>/dev/null || true
}
CODE=$(read_field code)
MESSAGE=$(read_field message)
MESSAGE=${MESSAGE:-release gate produced no answer}

if [ "$STATUS" -ne 0 ]; then
    if [ "$CODE" = already_published ] && [ "${RUN_ATTEMPT:-1}" -gt 1 ]; then
        echo "$IMAGE $VERSION is already published; allowed because this is re-run attempt ${RUN_ATTEMPT}"
        exit 0
    fi
    echo "Refusing $TAG: $MESSAGE" >&2
    exit "$STATUS"
fi

if [ -n "$CANDIDATE" ]; then
    echo "$MESSAGE (release candidate)"
else
    echo "$MESSAGE; tagged commit is on $MAIN_REF"
fi
