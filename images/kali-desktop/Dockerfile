FROM kalilinux/kali-rolling:latest

# Pin apt mirror to kali.download to avoid random mirror selection
RUN echo "deb http://kali.download/kali kali-rolling main contrib non-free non-free-firmware" > /etc/apt/sources.list

# Install kali packages
ARG KALI_METAPACKAGE=core
ENV DEBIAN_FRONTEND noninteractive
# kali-rolling is a rolling upstream, so this image cannot be byte-reproducible anyway; the
# package refresh is still opt-in so a rebuild of the same commit reuses its cache instead of
# pulling a new nightly package set. Refresh it deliberately: Run workflow -> upgrade_base.
# The package lists are fetched in the same step, so a refresh never upgrades from stale lists
# left in the build cache.
ARG APT_UPGRADE=false
RUN apt-get update && \
    if [ "$APT_UPGRADE" = "true" ]; then apt-get -y upgrade; fi
RUN apt-get -y install kali-linux-${KALI_METAPACKAGE}
RUN apt-get clean

# Install kali desktop
ARG KALI_DESKTOP=xfce
RUN apt-get -y install kali-desktop-${KALI_DESKTOP}
RUN apt-get -y install net-tools zsh vim curl libdatetime-perl

RUN useradd coder \
      --create-home \
      --shell=/usr/bin/zsh \
      --uid=1000 \
      --user-group && \
    echo "coder ALL=(ALL) NOPASSWD:ALL" >>/etc/sudoers.d/nopasswd

USER coder

# Provenance, last on purpose: an ARG is part of the cache key of every later RUN, and
# these change on every commit, so declared any earlier they rebuild the whole image.
# CI overwrites them; the defaults keep a local build honest. VERSION is namespaced with
# `ci/` so an untagged build can never masquerade as a release.
ARG VERSION=ci/dev
ARG GIT_SHA=unknown
ARG BUILD_CREATED=1970-01-01T00:00:00Z
ARG IMAGE_DESCRIPTION=Kali Linux desktop for Coder workspaces
LABEL org.opencontainers.image.title="coder-images-kali-desktop" \
      org.opencontainers.image.description="${IMAGE_DESCRIPTION}" \
      org.opencontainers.image.source="https://github.com/chrisbalmer/coder-images" \
      org.opencontainers.image.revision="${GIT_SHA}" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.created="${BUILD_CREATED}"
