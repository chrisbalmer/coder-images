# Pin the base image here. CI builds this image against the digest of exactly this
# version, so `docker build` and CI resolve the same layers. Changing BASE_VERSION is
# how you adopt a new base: a one-line, reviewable diff.
ARG BASE_NAME=ghcr.io/chrisbalmer/coder-images-base
ARG BASE_VERSION=2.2.0
# CI overrides BASE_REF with <name>@<digest>; locally it resolves to the pin above.
ARG BASE_REF=${BASE_NAME}:${BASE_VERSION}
# Digest CI actually resolved BASE_VERSION to; empty for a local build.
ARG BASE_DIGEST=
FROM ${BASE_REF}

# Run everything as root
USER root

# Install go — TARGETARCH is set automatically by Docker for multi-platform builds
ARG TARGETARCH
COPY images/golang/checksums.sha256 /tmp/checksums.sha256
RUN curl -LO "https://go.dev/dl/go1.27.1.linux-${TARGETARCH}.tar.gz" && \
    sha256sum --ignore-missing --check /tmp/checksums.sha256 && \
    tar -C /usr/local -xzvf go1.27.1.linux-${TARGETARCH}.tar.gz && \
    rm go1.27.1.linux-${TARGETARCH}.tar.gz

RUN apt-get update && \
    apt-get install -y \
      mysql-client postgresql-client && \
    apt-get clean

# Setup go env vars
ENV GOROOT /usr/local/go
ENV PATH $PATH:$GOROOT/bin

# Editor and debugger tools, pinned and installed next to the tools below. The module downloads
# are verified against the Go checksum database (sum.golang.org). The build-time GOPATH and cache
# are thrown away: everything the image ships lands in /usr/local/bin, which a workspace's home
# volume cannot hide.
ARG GOTOOLS_VERSION=v0.50.0
ARG GOPLS_VERSION=v0.23.0
ARG DELVE_VERSION=v1.27.2
RUN export GOPATH=/tmp/gopath GOCACHE=/tmp/gocache GOBIN=/usr/local/bin GOTOOLCHAIN=local && \
    go install "golang.org/x/tools/cmd/goimports@${GOTOOLS_VERSION}" && \
    go install "golang.org/x/tools/gopls@${GOPLS_VERSION}" && \
    go install "github.com/go-delve/delve/cmd/dlv@${DELVE_VERSION}" && \
    rm -rf /tmp/gopath /tmp/gocache

# Lint, release and live-reload tools, each pinned and checked against checksums.sha256 (a file
# with no line there is refused first: `--ignore-missing` alone would pass it).
ARG GOLANGCI_LINT_VERSION=2.14.0
ARG GORELEASER_VERSION=v2.18.2
ARG AIR_VERSION=1.67.4
RUN case "${TARGETARCH:-amd64}" in \
      amd64) ARCH=amd64; GORELEASER_ARCH=x86_64 ;; \
      arm64) ARCH=arm64; GORELEASER_ARCH=arm64 ;; \
      *) echo "tools: unsupported TARGETARCH '${TARGETARCH}'" >&2; exit 1 ;; \
    esac && \
    mkdir /tmp/tools && cd /tmp/tools && \
    curl -fsSLO "https://github.com/golangci/golangci-lint/releases/download/v${GOLANGCI_LINT_VERSION}/golangci-lint-${GOLANGCI_LINT_VERSION}-linux-${ARCH}.tar.gz" && \
    curl -fsSLO "https://github.com/goreleaser/goreleaser/releases/download/${GORELEASER_VERSION}/goreleaser_Linux_${GORELEASER_ARCH}.tar.gz" && \
    curl -fsSLO "https://github.com/air-verse/air/releases/download/v${AIR_VERSION}/air_${AIR_VERSION}_linux_${ARCH}" && \
    for f in *; do \
      grep -q "  ${f}\$" /tmp/checksums.sha256 || { echo "no checksum for ${f}" >&2; exit 1; }; \
    done && \
    sha256sum --ignore-missing --check /tmp/checksums.sha256 && \
    tar xzf "golangci-lint-${GOLANGCI_LINT_VERSION}-linux-${ARCH}.tar.gz" --strip-components=1 \
      "golangci-lint-${GOLANGCI_LINT_VERSION}-linux-${ARCH}/golangci-lint" && \
    tar xzf "goreleaser_Linux_${GORELEASER_ARCH}.tar.gz" goreleaser && \
    install -m 0755 golangci-lint goreleaser /usr/local/bin/ && \
    install -m 0755 "air_${AIR_VERSION}_linux_${ARCH}" /usr/local/bin/air && \
    cd / && rm -rf /tmp/tools

# Set back to coder user
USER coder

# The workspace's own GOPATH (module cache, `go install`) is user data on the home volume.
ENV GOPATH=/home/coder/go
ENV GOBIN=$GOPATH/bin
ENV PATH=$PATH:$GOBIN

# Smoke test: the tools run as the workspace user (uid 1000, no sudo), on each architecture
# built, so a binary for the wrong architecture or one that needs root fails the build.
RUN test "$(id -u):$(id -g)" = 1000:1000 && \
    go version && \
    golangci-lint --version && \
    goreleaser --version && \
    air -v && \
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
ARG IMAGE_DESCRIPTION=Go development environment
LABEL org.opencontainers.image.title="coder-images-golang" \
      org.opencontainers.image.description="${IMAGE_DESCRIPTION}" \
      org.opencontainers.image.base.name="${BASE_NAME}:${BASE_VERSION}" \
      org.opencontainers.image.base.digest="${BASE_DIGEST}" \
      org.opencontainers.image.source="https://github.com/chrisbalmer/coder-images" \
      org.opencontainers.image.revision="${GIT_SHA}" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.created="${BUILD_CREATED}"
