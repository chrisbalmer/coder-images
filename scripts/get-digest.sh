#!/bin/bash
# Get the digest of a published image
# Usage: ./scripts/get-digest.sh <image-name> <tag>

set -e

if [ $# -ne 2 ]; then
    echo "Usage: $0 <image-name> <tag>"
    echo ""
    echo "Examples:"
    echo "  $0 golang 1.2.0"
    echo "  $0 base latest"
    echo "  $0 xsoar main-abc1234"
    echo ""
    echo "Available images: base, golang, xsoar, terraform, podman, kali-desktop, ubuntu-desktop"
    exit 1
fi

IMAGE_NAME=$1
TAG=$2
REGISTRY="ghcr.io"
OWNER="chrisbalmer"
FULL_IMAGE="${REGISTRY}/${OWNER}/coder-images-${IMAGE_NAME}:${TAG}"

echo "Fetching digest for: $FULL_IMAGE"
echo ""

# Try to get digest without pulling
echo "Attempting to get digest from registry..."
if command -v skopeo &> /dev/null; then
    # Use skopeo if available (faster, no pull needed)
    DIGEST=$(skopeo inspect docker://${FULL_IMAGE} | jq -r '.Digest')
    if [ -n "$DIGEST" ] && [ "$DIGEST" != "null" ]; then
        echo "✅ Digest (via skopeo): ${DIGEST}"
        echo ""
        echo "Full image reference:"
        echo "${REGISTRY}/${OWNER}/coder-images-${IMAGE_NAME}@${DIGEST}"
        exit 0
    fi
fi

# Fall back to docker pull + inspect
echo "Pulling image to get digest..."
if docker pull "${FULL_IMAGE}" > /dev/null 2>&1; then
    DIGEST=$(docker inspect --format='{{index .RepoDigests 0}}' "${FULL_IMAGE}" 2>/dev/null || echo "")

    if [ -z "$DIGEST" ]; then
        echo "❌ Error: Could not get digest from pulled image"
        exit 1
    fi

    echo "✅ Image pulled successfully"
    echo ""
    echo "Full image reference:"
    echo "${DIGEST}"
    echo ""
    echo "Docker Compose format:"
    echo "  image: ${DIGEST}"
    echo ""
    echo "Kubernetes format:"
    echo "  image: ${DIGEST}"
    echo ""
    echo "Just the digest:"
    echo "${DIGEST##*@}"
else
    echo "❌ Error: Could not pull image ${FULL_IMAGE}"
    echo ""
    echo "Possible reasons:"
    echo "  1. Image/tag doesn't exist"
    echo "  2. Not authenticated (run: echo \$GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin)"
    echo "  3. No access to the repository"
    exit 1
fi
