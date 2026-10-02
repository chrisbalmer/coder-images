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

USER root

COPY src/cortex/requirements.txt /tmp/requirements.txt

# The venv lives outside /home/coder: a workspace mounts its persistent home volume there, and a
# Kubernetes volume is not seeded from the image, so anything installed under it disappears. It
# is owned by coder, so `pip install` into it still works without sudo.
RUN install -d -o coder -g coder /opt/venvs/cortex

USER coder

RUN python3 -m venv /opt/venvs/cortex && \
    /opt/venvs/cortex/bin/pip install --no-cache-dir --upgrade pip && \
    /opt/venvs/cortex/bin/pip install --no-cache-dir -r /tmp/requirements.txt

# demisto-sdk pins an old uv (0.1.45) as a dependency, and `demisto-sdk setup-env` runs it by
# path (<venv>/bin/uv), so it stays. On PATH, though, it would shadow base's current uv while
# `uvx` (which 0.1.45 lacks) still resolved to base's: two versions of one tool. A directory
# holding only uv and uvx, ahead of the venv, gives the shell base's for both; python and pip
# still come from the venv.
USER root
RUN install -d /opt/uv/bin && \
    ln -s /usr/local/bin/uv /opt/uv/bin/uv && \
    ln -s /usr/local/bin/uvx /opt/uv/bin/uvx
USER coder

# Put venv on PATH — works for all shells, survives dotfile replacement
ENV VIRTUAL_ENV=/opt/venvs/cortex
ENV PATH="/opt/uv/bin:/opt/venvs/cortex/bin:$PATH"

# Smoke test: the SDK runs as the workspace user (uid 1000, no sudo), on each architecture built.
RUN test "$(id -u):$(id -g)" = 1000:1000 && \
    demisto-sdk --version && \
    test "$(uv --version)" = "$(/usr/local/bin/uv --version)" && \
    /opt/venvs/cortex/bin/uv --version

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
ARG IMAGE_DESCRIPTION=Palo Alto Cortex (XSOAR/XSIAM) development environment
LABEL org.opencontainers.image.title="coder-images-cortex" \
      org.opencontainers.image.description="${IMAGE_DESCRIPTION}" \
      org.opencontainers.image.base.name="${BASE_NAME}:${BASE_VERSION}" \
      org.opencontainers.image.base.digest="${BASE_DIGEST}" \
      org.opencontainers.image.source="https://github.com/chrisbalmer/coder-images" \
      org.opencontainers.image.revision="${GIT_SHA}" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.created="${BUILD_CREATED}"
