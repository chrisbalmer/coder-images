FROM kalilinux/kali-rolling:latest

# Pin apt mirror to kali.download to avoid random mirror selection
RUN echo "deb http://kali.download/kali kali-rolling main contrib non-free non-free-firmware" > /etc/apt/sources.list

# Install kali packages. DEBIAN_FRONTEND is a build ARG, so it doesn't persist into the workspace.
ARG KALI_METAPACKAGE=core
ARG KALI_DESKTOP=xfce
# The security-lab toolset: reverse engineering, forensics, crypto/stego, web, exploitation and
# passwords, plus static malware analysis (Ghidra, YARA, pefile) and pwntools for CTFs.
# Everything outside /home/coder resets on every workspace restart, so lab tools live here, not
# in a user's `apt install`. No Wine, on purpose: it would let Windows samples run.
ARG KALI_TOOLS="kali-tools-reverse-engineering kali-tools-forensics kali-tools-crypto-stego kali-tools-web kali-tools-exploitation kali-tools-passwords ghidra yara python3-pefile python3-pwntools firefox-esr git sudo"
ARG DEBIAN_FRONTEND=noninteractive
# KasmVNC serves the desktop to the browser; the template's kasmvnc module only configures and
# starts it when it's already installed. Each package must have a line in checksums.sha256.
ARG KASMVNC_VERSION=1.5.0
ARG TARGETARCH
COPY images/kali-desktop/checksums.sha256 /tmp/checksums.sha256
# kali-rolling is a rolling upstream, so this image cannot be byte-reproducible anyway; the
# package refresh is still opt-in so a rebuild of the same commit reuses its cache instead of
# pulling a new nightly package set. Refresh it deliberately: Run workflow -> upgrade_base.
# One step fetches the lists, installs and cleans up, so a refresh never upgrades from stale lists
# left in the build cache and no layer keeps the lists or the package archive. KasmVNC installs in
# the same step, against the same package lists as everything else.
ARG APT_UPGRADE=false
RUN case "${TARGETARCH:-amd64}" in \
      amd64|arm64) ;; \
      *) echo "unsupported TARGETARCH: ${TARGETARCH}" >&2; exit 1 ;; \
    esac && \
    apt-get update && \
    if [ "$APT_UPGRADE" = "true" ]; then apt-get -y upgrade; fi && \
    apt-get -y install \
      kali-linux-${KALI_METAPACKAGE} \
      kali-desktop-${KALI_DESKTOP} \
      net-tools zsh vim curl libdatetime-perl \
      ${KALI_TOOLS} && \
    deb="kasmvncserver_kali-rolling_${KASMVNC_VERSION}_${TARGETARCH:-amd64}.deb" && \
    curl -fsSL -o "/tmp/${deb}" "https://github.com/kasmtech/KasmVNC/releases/download/v${KASMVNC_VERSION}/${deb}" && \
    { grep -q "  ${deb}\$" /tmp/checksums.sha256 || { echo "no checksum for ${deb}" >&2; exit 1; }; } && \
    (cd /tmp && sha256sum --ignore-missing --check /tmp/checksums.sha256) && \
    apt-get -y install "/tmp/${deb}" && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* "/tmp/${deb}" /tmp/checksums.sha256 && \
    ! ldd /usr/bin/Xkasmvnc | grep "not found" && \
    { /usr/bin/Xkasmvnc -version 2>&1 || true; } | grep -qi kasmvnc

RUN useradd coder \
      --create-home \
      --shell=/usr/bin/zsh \
      --uid=1000 \
      --user-group && \
    # KasmVNC's default config reads the snakeoil key, which only ssl-cert members can.
    usermod -aG ssl-cert coder && \
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
