# Pin the base image here. CI builds this image against the digest of exactly this
# version, so `docker build` and CI resolve the same layers. Changing BASE_VERSION is
# how you adopt a new base: a one-line, reviewable diff.
ARG BASE_NAME=ghcr.io/chrisbalmer/coder-images-base
ARG BASE_VERSION=2.3.0
# CI overrides BASE_REF with <name>@<digest>; locally it resolves to the pin above.
ARG BASE_REF=${BASE_NAME}:${BASE_VERSION}
# Digest CI actually resolved BASE_VERSION to; empty for a local build.
ARG BASE_DIGEST=
FROM ${BASE_REF}

# Run everything as root
USER root

# KasmVNC serves the desktop to the browser; the template's kasmvnc module only configures and
# starts it when it's already installed. KasmVNC publishes no Ubuntu 26.04 (resolute) package
# yet, so this installs the noble (24.04) build: every library it depends on exists in 26.04, and
# the ldd check below fails the build if one goes missing. Switch to the resolute package when a
# KasmVNC release ships one. Each package must have a line in checksums.sha256.
ARG KASMVNC_VERSION=1.5.0
ARG KASMVNC_DIST=noble
ARG TARGETARCH
COPY images/ubuntu-desktop/checksums.sha256 /tmp/checksums.sha256

# Ubuntu's own firefox package is a stub that installs the snap, which can't run in a container,
# so Firefox comes from Mozilla's APT repository, pinned above Ubuntu's. The key is checked by
# fingerprint before apt trusts it.
ARG MOZILLA_KEY_FPR=35BAA0B33E9EB396F59CA838C0BA5CE6DC6315A3
RUN install -d -m 0755 /etc/apt/keyrings && \
    curl -fsSL https://packages.mozilla.org/apt/repo-signing-key.gpg -o /etc/apt/keyrings/packages.mozilla.org.asc && \
    gpg --show-keys --with-colons /etc/apt/keyrings/packages.mozilla.org.asc | grep -q "^fpr:::::::::${MOZILLA_KEY_FPR}:" && \
    echo "deb [signed-by=/etc/apt/keyrings/packages.mozilla.org.asc] https://packages.mozilla.org/apt mozilla main" \
      > /etc/apt/sources.list.d/mozilla.list && \
    printf 'Package: *\nPin: origin packages.mozilla.org\nPin-Priority: 1000\n' > /etc/apt/preferences.d/mozilla

# Xfce only: the template starts Xfce, and Unity needs 3D compositing a VNC session doesn't have.
# No `apt upgrade`: this image inherits a patched base, and upgrading again would make the
# layer depend on the mirror's state at build time instead of on this commit.
RUN case "${TARGETARCH:-amd64}" in \
      amd64|arm64) ;; \
      *) echo "unsupported TARGETARCH: ${TARGETARCH}" >&2; exit 1 ;; \
    esac && \
    deb="kasmvncserver_${KASMVNC_DIST}_${KASMVNC_VERSION}_${TARGETARCH:-amd64}.deb" && \
    cd /tmp && \
    curl -fsSLO "https://github.com/kasmtech/KasmVNC/releases/download/v${KASMVNC_VERSION}/${deb}" && \
    { grep -q "  ${deb}\$" /tmp/checksums.sha256 || { echo "no checksum for ${deb}" >&2; exit 1; }; } && \
    sha256sum --ignore-missing --check /tmp/checksums.sha256 && \
    apt update && \
    apt install --yes xfce4 xfce4-terminal dbus-x11 firefox "/tmp/${deb}" && \
    apt clean && \
    rm -f "/tmp/${deb}" /tmp/checksums.sha256 && \
    # KasmVNC's default config reads the snakeoil key, which only ssl-cert members can.
    usermod -aG ssl-cert coder && \
    ! ldd /usr/bin/Xkasmvnc | grep "not found" && \
    { /usr/bin/Xkasmvnc -version 2>&1 || true; } | grep -qi kasmvnc

# Set back to coder user
USER coder

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
ARG IMAGE_DESCRIPTION=Ubuntu with a desktop environment for Coder workspaces
LABEL org.opencontainers.image.title="coder-images-ubuntu-desktop" \
      org.opencontainers.image.description="${IMAGE_DESCRIPTION}" \
      org.opencontainers.image.base.name="${BASE_NAME}:${BASE_VERSION}" \
      org.opencontainers.image.base.digest="${BASE_DIGEST}" \
      org.opencontainers.image.source="https://github.com/chrisbalmer/coder-images" \
      org.opencontainers.image.revision="${GIT_SHA}" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.created="${BUILD_CREATED}"
