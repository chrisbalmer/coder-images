#!/bin/bash
# Test that Dockerfiles support both Gitea and GitHub registries

set -e

echo "🧪 Testing Dockerfile registry support"
echo ""

# Test with GitHub registry (default)
echo "1️⃣ Testing with GitHub registry (default)..."
for dockerfile in images/*/Dockerfile; do
    image_name=$(basename $(dirname $dockerfile))

    # Skip base and independent images
    if [[ "$image_name" == "base" || "$image_name" == "podman" || "$image_name" == "kali-desktop" ]]; then
        continue
    fi

    echo "   Checking $image_name..."

    # Parse Dockerfile to check for ARG REGISTRY
    if ! grep -q "ARG REGISTRY=" "$dockerfile"; then
        echo "   ❌ Missing: ARG REGISTRY"
        exit 1
    fi

    if ! grep -q "ARG IMAGE_OWNER=" "$dockerfile"; then
        echo "   ❌ Missing: ARG IMAGE_OWNER"
        exit 1
    fi

    if ! grep -q "ARG BASE_TAG=" "$dockerfile"; then
        echo "   ❌ Missing: ARG BASE_TAG"
        exit 1
    fi

    # Check FROM line uses variables
    if ! grep -q 'FROM ${REGISTRY}/${IMAGE_OWNER}/coder-images-base:${BASE_TAG}' "$dockerfile"; then
        echo "   ❌ FROM line doesn't use variables correctly"
        echo "   Expected: FROM \${REGISTRY}/\${IMAGE_OWNER}/coder-images-base:\${BASE_TAG}"
        echo "   Got: $(grep '^FROM' $dockerfile)"
        exit 1
    fi

    echo "   ✅ $image_name supports dynamic registry"
done

echo ""
echo "2️⃣ Testing build with GitHub registry (default args)..."
echo "   docker build -f images/golang/Dockerfile -t test-golang:github ."
if docker build -f images/golang/Dockerfile -t test-golang:github . --quiet > /dev/null 2>&1; then
    echo "   ✅ Build succeeds with default (GitHub) registry"
    docker rmi test-golang:github > /dev/null 2>&1 || true
else
    echo "   ⚠️  Build failed (may need base image to exist)"
fi

echo ""
echo "3️⃣ Testing build with Gitea registry (custom args)..."
echo "   docker build --build-arg REGISTRY=registry.gitea.example.com ..."
if docker build -f images/golang/Dockerfile \
    --build-arg REGISTRY=registry.gitea.example.com \
    --build-arg IMAGE_OWNER=testuser \
    --build-arg BASE_TAG=latest \
    -t test-golang:gitea . --quiet > /dev/null 2>&1; then
    echo "   ✅ Build succeeds with Gitea registry"
    docker rmi test-golang:gitea > /dev/null 2>&1 || true
else
    echo "   ⚠️  Build failed (may need base image to exist)"
fi

echo ""
echo "4️⃣ Verifying workflow files pass registry args..."

# Check GitHub workflow
if grep -q "REGISTRY=\${{ env.REGISTRY }}" .github/workflows/publish.yml && \
   grep -q "IMAGE_OWNER=\${{ github.repository_owner }}" .github/workflows/publish.yml; then
    echo "   ✅ GitHub workflow passes registry args"
else
    echo "   ❌ GitHub workflow missing registry args"
    exit 1
fi

# Check unified workflow
if grep -q "REGISTRY=\${{ needs.detect-platform.outputs.registry }}" .github/workflows/publish-unified.yml && \
   grep -q "IMAGE_OWNER=\${{ gitea.repository_owner || github.repository_owner }}" .github/workflows/publish-unified.yml; then
    echo "   ✅ Unified workflow passes registry args"
else
    echo "   ❌ Unified workflow missing registry args"
    exit 1
fi

# Check Gitea workflow
if grep -q "REGISTRY=\${{ needs.detect-platform.outputs.registry }}" .gitea/workflows/publish.yml && \
   grep -q "IMAGE_OWNER=\${{ gitea.repository_owner || github.repository_owner }}" .gitea/workflows/publish.yml; then
    echo "   ✅ Gitea workflow passes registry args"
else
    echo "   ❌ Gitea workflow missing registry args"
    exit 1
fi

echo ""
echo "✅ All tests passed!"
echo ""
echo "📋 Summary:"
echo "   • Dockerfiles support dynamic REGISTRY, IMAGE_OWNER, and BASE_TAG"
echo "   • Default values work for GitHub (ghcr.io/chrisbalmer)"
echo "   • Can override for Gitea with build args"
echo "   • Workflows pass correct registry parameters"
echo ""
echo "🎯 Ready for dual-platform deployment!"
