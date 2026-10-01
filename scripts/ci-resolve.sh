#!/usr/bin/env bash
# The resolve job, shared by both CI platforms: decide what to build (or release), resolve
# each dependent's base pin to a digest, and write the job outputs.
#
# Environment, set by the workflow:
#   EVENT BEFORE PR_BASE_SHA REF REF_NAME DEFAULT_BRANCH   what triggered the run
#   REGISTRY OWNER REPOSITORY                             where images live, who is running
#   INPUT_IMAGES INPUT_ALL INPUT_UPGRADE_BASE             workflow_dispatch inputs
#   REGISTRY_USERNAME REGISTRY_PASSWORD RUN_ATTEMPT       registry reads, release re-runs
#   GITHUB_OUTPUT                                         where the outputs go

set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT=${GITHUB_OUTPUT:-/dev/stdout}

# An empty context would publish ghcr.io//coder-images-cortex and report success.
for var in REGISTRY OWNER REPOSITORY; do
    if [ -z "${!var:-}" ]; then
        echo "::error::$var is empty; the platform context or repository variable is missing"
        exit 1
    fi
done
# OCI repository names are lowercase: a fork owned by MyName publishes to ghcr.io/myname.
OWNER=$(tr '[:upper:]' '[:lower:]' <<<"$OWNER")
PREFIX="$REGISTRY/$OWNER/coder-images"

has_commit() { git cat-file -e "${1}^{commit}" 2> /dev/null; }

# What to diff against. A tag push and a brand new branch have none, and that means "no diff":
# guessing HEAD^ would rebuild and republish the previous commit's images. The one exception is
# a repository's first commit on the default branch: there is nothing to diff against, and
# nothing published yet, so it builds every image.
COMPARE=''
FIRST_COMMIT=false
case "$EVENT" in
    pull_request) COMPARE=${PR_BASE_SHA:-} ;;
    workflow_dispatch) if has_commit HEAD^; then COMPARE=HEAD^; fi ;;
    push)
        if [ -n "${BEFORE:-}" ] && [ "$BEFORE" != 0000000000000000000000000000000000000000 ]; then
            COMPARE=$BEFORE
        elif [ "$REF" = "refs/heads/$DEFAULT_BRANCH" ] && ! has_commit HEAD^; then
            FIRST_COMMIT=true
        fi ;;
esac
# The compare commit can vanish under a force push; degrade to the last commit.
if [ -n "$COMPARE" ] && ! has_commit "$COMPARE"; then
    echo "::warning::${COMPARE} is not in this clone; comparing against HEAD^"
    COMPARE=''
    if has_commit HEAD^; then COMPARE=HEAD^; fi
fi

# Both platforms report event_name=push for a tag push; only the ref says it is a release.
case "$REF" in
    refs/tags/*)
        EVENT=tag
        bash scripts/validate-release-tag.sh "$REGISTRY" "$OWNER" "$REF" origin/main ;;
esac

ARGS=(--event "$EVENT" --ref "$REF" --ref-name "$REF_NAME" --default-branch "$DEFAULT_BRANCH"
      --registry "$REGISTRY" --repository "$REPOSITORY" --summary)
if [ "${INPUT_UPGRADE_BASE:-}" = true ]; then ARGS+=(--upgrade-base true); fi
if [ -n "${INPUT_IMAGES:-}" ]; then
    ARGS+=(--images "$INPUT_IMAGES")
elif [ "${INPUT_ALL:-}" = true ] || [ "$FIRST_COMMIT" = true ]; then
    ARGS+=(--all)
elif [ -n "$COMPARE" ]; then
    ARGS+=(--changed-base "$COMPARE")
fi
PLAN=$(python3 scripts/ci-graph.py plan "${ARGS[@]}")
jq . <<<"$PLAN"
if [ "$EVENT" = tag ] && [ "$(jq -r '.publish.allowed' <<<"$PLAN")" != true ]; then
    echo "::error::$REF would build without publishing: $(jq -r '.publish.reason' <<<"$PLAN")"
    exit 1
fi

# Resolve every pinned base version before any multi-arch build starts. A pin that does not
# resolve fails only the dependents that use it (their own job reports it), so base and the
# standalone images still build: that is how a first base release becomes possible at all.
MAP='{}'
if [ "$(jq '.digest_refs | length' <<<"$PLAN")" != 0 ]; then
    STATUS=0
    MAP=$(jq -c '.digest_refs' <<<"$PLAN" \
        | python3 scripts/base-digest.py --registry "$REGISTRY" --owner "$OWNER" --quiet) || STATUS=$?
    case "$MAP" in '{'*) ;; *) MAP='{}' ;; esac
    if [ "$STATUS" != 0 ]; then
        echo "::warning::a pinned base version is not in $REGISTRY; the dependents that pin it will not build"
    fi
fi

# Give each dependent its base reference, pinned by digest, so the build job has nothing left
# to look up. An empty base_digest means the pin did not resolve: the dependent job fails if it
# would publish, and is skipped on a pull request, where the base release may not be cut yet.
DEPENDENT=$(jq -c --argjson map "$MAP" --arg prefix "$PREFIX" '
    .dependent | map(
        (.from + ":" + .base_version) as $pin
        | ($map[$pin] // "") as $digest
        | . + {base_name: ($prefix + "-" + $pin),
               base_digest: $digest,
               base_ref: (if $digest == "" then "" else $prefix + "-" + .from + "@" + $digest end)})
' <<<"$PLAN")

{
    printf 'image_prefix=%s\n' "$PREFIX"
    printf 'base=%s\n' "$(jq -c '.base // empty' <<<"$PLAN")"
    printf 'standalone=%s\n' "$(jq -c '.standalone' <<<"$PLAN")"
    printf 'dependent=%s\n' "$DEPENDENT"
    printf 'release=%s\n' "$(jq -c '.release // empty' <<<"$PLAN")"
    printf 'release_publish=%s\n' "$(jq -r '.release.publish // "false"' <<<"$PLAN")"
} >> "$OUTPUT"
