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

# No `apt upgrade`: this image inherits a patched base, and upgrading again would make the
# layer depend on the mirror's state at build time instead of on this commit.
RUN apt update && \
    apt install --yes \
      ubuntu-unity-desktop xfce4 libdatetime-perl dbus-x11 && \
    apt clean

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
