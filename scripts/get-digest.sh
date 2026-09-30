#!/usr/bin/env bash
# Print the digest of a published image, and the pinned-ready reference for it.
#
# Usage:
#   scripts/get-digest.sh <image> <version>      digest for one published image
#   scripts/get-digest.sh --pins                 every base pin, resolved
#   scripts/get-digest.sh --help
#
# Options (any position):
#   --registry <host>   default ghcr.io
#   --owner <name>      default chrisbalmer
#   --prefix <name>     default coder-images
#
# Examples:
#   scripts/get-digest.sh cortex 2.0.0
#   scripts/get-digest.sh base 2.0.0 --registry registry.example.com --owner library
#   scripts/get-digest.sh --pins --registry registry.example.com --owner library

set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

PY=$(command -v python3 || command -v python)
[ -n "$PY" ] || { echo "python3 is required" >&2; exit 2; }

usage() {
    awk 'NR > 1 { if (!/^#/) exit; sub(/^# ?/, ""); print }' "$0"
    echo
    echo "Available images: $("$PY" scripts/ci-graph.py images | tr -d '[]"' | tr ',' ' ')"
}

REGISTRY=${REGISTRY:-ghcr.io}
OWNER=${IMAGE_OWNER:-chrisbalmer}
PREFIX=coder-images
MODE=image
POSITIONAL=()

while [ $# -gt 0 ]; do
    case "$1" in
        --registry) REGISTRY="${2:?--registry needs a value}"; shift 2 ;;
        --owner)    OWNER="${2:?--owner needs a value}"; shift 2 ;;
        --prefix)   PREFIX="${2:?--prefix needs a value}"; shift 2 ;;
        --pins)     MODE=pins; shift ;;
        -h|--help)  usage; exit 0 ;;
        -*)         echo "Unknown option: $1" >&2; usage >&2; exit 1 ;;
        *)          POSITIONAL+=("$1"); shift ;;
    esac
done

if [ "$MODE" = pins ]; then
    "$PY" scripts/ci-graph.py pins \
        | "$PY" scripts/base-digest.py --registry "$REGISTRY" --owner "$OWNER" --prefix "$PREFIX"
    exit 0
fi

if [ "${#POSITIONAL[@]}" -lt 2 ]; then
    usage >&2
    exit 1
fi

IMAGE="${POSITIONAL[0]}"
VERSION="${POSITIONAL[1]}"

if ! "$PY" scripts/ci-graph.py images | grep -q "\"$IMAGE\""; then
    echo "Unknown image: $IMAGE" >&2
    usage >&2
    exit 1
fi

FULL="${REGISTRY}/${OWNER}/${PREFIX}-${IMAGE}:${VERSION}"
echo "Resolving: ${FULL}" >&2
DIGEST=$(printf '["%s:%s"]' "$IMAGE" "$VERSION" \
    | "$PY" scripts/base-digest.py --registry "$REGISTRY" --owner "$OWNER" \
        --prefix "$PREFIX" --quiet \
    | "$PY" -c 'import json,sys; values=list(json.load(sys.stdin).values()); print(values[0] if values else "")')

if [ -z "$DIGEST" ]; then
    echo "Could not resolve ${FULL}" >&2
    echo "Has the release been cut? Try: scripts/release.sh ${IMAGE} ${VERSION}" >&2
    exit 1
fi

PINNED="${REGISTRY}/${OWNER}/${PREFIX}-${IMAGE}@${DIGEST}"
echo
echo "Digest:      ${DIGEST}"
echo "Pinned ref:  ${PINNED}"
echo
echo "Docker / Kubernetes:"
echo "  image: ${PINNED}"
