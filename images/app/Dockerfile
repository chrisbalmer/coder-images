# Pin the parent image here, exactly as the base's dependents pin base: CI builds this image
# against the digest of exactly this golang version, so `docker build` and CI resolve the same
# layers. Changing BASE_VERSION is how you adopt a new golang release: a one-line, reviewable diff.
ARG BASE_NAME=ghcr.io/chrisbalmer/coder-images-golang
ARG BASE_VERSION=2.4.0
# CI overrides BASE_REF with <name>@<digest>; locally it resolves to the pin above.
ARG BASE_REF=${BASE_NAME}:${BASE_VERSION}
# Digest CI actually resolved BASE_VERSION to; empty for a local build.
ARG BASE_DIGEST=
FROM ${BASE_REF}

# Run everything as root
USER root

COPY images/app/checksums.sha256 /tmp/checksums.sha256

# Go comes from golang, and Node.js 22 and npm from base. pnpm is the standalone release build;
# helm matches infra's. Each is pinned and checked against checksums.sha256 (a file with no line
# there is refused first: `--ignore-missing` alone would pass it).
ARG TARGETARCH
ARG PNPM_VERSION=v12.6.0
ARG HELM_VERSION=v3.22.0
RUN case "${TARGETARCH:-amd64}" in \
      amd64) ARCH=amd64; PNPM_ARCH=x64 ;; \
      arm64) ARCH=arm64; PNPM_ARCH=arm64 ;; \
      *) echo "tools: unsupported TARGETARCH '${TARGETARCH}'" >&2; exit 1 ;; \
    esac && \
    mkdir /tmp/tools && cd /tmp/tools && \
    curl -fsSLO "https://github.com/pnpm/pnpm/releases/download/${PNPM_VERSION}/pnpm-linux-${PNPM_ARCH}.tar.gz" && \
    curl -fsSLO "https://get.helm.sh/helm-${HELM_VERSION}-linux-${ARCH}.tar.gz" && \
    for f in *; do \
      grep -q "  ${f}\$" /tmp/checksums.sha256 || { echo "no checksum for ${f}" >&2; exit 1; }; \
    done && \
    sha256sum --ignore-missing --check /tmp/checksums.sha256 && \
    mkdir /usr/local/lib/pnpm && \
    tar xzf "pnpm-linux-${PNPM_ARCH}.tar.gz" -C /usr/local/lib/pnpm && \
    ln -s /usr/local/lib/pnpm/pnpm /usr/local/bin/pnpm && \
    tar xzf "helm-${HELM_VERSION}-linux-${ARCH}.tar.gz" "linux-${ARCH}/helm" && \
    install -m 0755 "linux-${ARCH}/helm" /usr/local/bin/helm && \
    cd / && rm -rf /tmp/tools

# Set back to coder user
USER coder

# Smoke test: the tools run as the workspace user (uid 1000, no sudo), on each architecture
# built, so a binary for the wrong architecture or one that needs root fails the build.
RUN test "$(id -u):$(id -g)" = 1000:1000 && \
    pnpm --version && \
    helm version --short && \
    node --version && \
    go version && \
    echo "package p" | goimports && \
    gopls version && \
    dlv version

# Provenance, last on purpose: an ARG is part of the cache key of every later RUN, and
# these change on every commit, so declared any earlier they rebuild the whole image.
# CI overwrites them; the defaults keep a local build honest. VERSION is namespaced with
# `ci/` so an untagged build can never masquerade as a release.
# The base ARGs are declared before FROM, so this stage must re-declare them to use them.
ARG BASE_NAME
ARG BASE_VERSION
ARG BASE_DIGEST
ARG VERSION=ci/dev
ARG GIT_SHA=unknown
ARG BUILD_CREATED=1970-01-01T00:00:00Z
ARG IMAGE_DESCRIPTION=Go and React application development: golang plus pnpm and Helm
LABEL org.opencontainers.image.title="coder-images-app" \
      org.opencontainers.image.description="${IMAGE_DESCRIPTION}" \
      org.opencontainers.image.base.name="${BASE_NAME}:${BASE_VERSION}" \
      org.opencontainers.image.base.digest="${BASE_DIGEST}" \
      org.opencontainers.image.source="https://github.com/chrisbalmer/coder-images" \
      org.opencontainers.image.revision="${GIT_SHA}" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.created="${BUILD_CREATED}"
