FROM kalilinux/kali-rolling:latest

# Pin apt mirror to kali.download to avoid random mirror selection
RUN echo "deb http://kali.download/kali kali-rolling main contrib non-free non-free-firmware" > /etc/apt/sources.list

# Install kali packages. DEBIAN_FRONTEND is a build ARG, so it doesn't persist into the workspace.
ARG KALI_METAPACKAGE=core
ARG KALI_DESKTOP=xfce
ARG DEBIAN_FRONTEND=noninteractive
ARG TARGETARCH
# kali-rolling is a rolling upstream, so this image cannot be byte-reproducible anyway; the
# package refresh is still opt-in so a rebuild of the same commit reuses its cache instead of
# pulling a new nightly package set. Refresh it deliberately: Run workflow -> upgrade_base.
ARG APT_UPGRADE=false

# The install is split into layers, ordered from the least to the most likely to change, so an
# edit to one tool group rebuilds (and every node re-pulls) only that layer and the ones after it.
# Each layer fetches the package lists, installs and cleans up in one step, so no layer keeps the
# lists or the package archive and none installs from stale lists left in the build cache.
# Everything outside /home/coder resets on every workspace restart, so lab tools live here, not in
# a user's `apt install`.

# 1. The desktop: Kali core, Xfce, a browser and the basics.
#
# No screen locker. The coder user has no password, on purpose (access is gated by the Coder
# session), so a lock screen locks the user out of their own desktop. Removing the locker beats
# configuring it off: no setting in a persistent home can turn it back on. kali-desktop-xfce
# depends on xfce4-screensaver, so that (empty) metapackage is purged with the locker; its other
# dependencies are marked manually installed first, so `apt autoremove` keeps the desktop.
# The apt pin keeps any later install from bringing a locker back. KasmVNC needs nothing else:
# its X server ignores screen blanking and DPMS, and its idle timeouts default to never.
RUN case "${TARGETARCH:-amd64}" in \
      amd64|arm64) ;; \
      *) echo "unsupported TARGETARCH: ${TARGETARCH}" >&2; exit 1 ;; \
    esac && \
    apt-get update && \
    if [ "$APT_UPGRADE" = "true" ]; then apt-get -y upgrade; fi && \
    apt-get -y install \
      kali-linux-${KALI_METAPACKAGE} \
      kali-desktop-${KALI_DESKTOP} \
      net-tools zsh vim curl libdatetime-perl git sudo firefox-esr iputils-ping && \
    keep=$(dpkg-query -W -f='${Depends}, ${Recommends}\n' "kali-desktop-${KALI_DESKTOP}" | \
      tr ',|' '\n\n' | sed -E 's/\(.*//; s/:any//; s/[[:space:]]//g' | sort -u) && \
    apt-mark manual $(dpkg-query -W -f='${db:Status-Abbrev} ${Package}\n' $keep 2>/dev/null | \
      awk '$1 == "ii" && $2 != "xfce4-screensaver" { print $2 }') >/dev/null && \
    apt-get -y purge "kali-desktop-${KALI_DESKTOP}" xfce4-screensaver light-locker xscreensaver && \
    printf 'Package: xfce4-screensaver light-locker xscreensaver mate-screensaver gnome-screensaver\nPin: version *\nPin-Priority: -1\n' \
      > /etc/apt/preferences.d/no-screen-locker && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 2. KasmVNC serves the desktop to the browser; the template's kasmvnc module only configures and
# starts it when it's already installed. Each package must have a line in checksums.sha256.
ARG KASMVNC_VERSION=1.5.0
COPY images/kali-desktop/checksums.sha256 /tmp/checksums.sha256
RUN apt-get update && \
    deb="kasmvncserver_kali-rolling_${KASMVNC_VERSION}_${TARGETARCH:-amd64}.deb" && \
    curl -fsSL -o "/tmp/${deb}" "https://github.com/kasmtech/KasmVNC/releases/download/v${KASMVNC_VERSION}/${deb}" && \
    { grep -q "  ${deb}\$" /tmp/checksums.sha256 || { echo "no checksum for ${deb}" >&2; exit 1; }; } && \
    (cd /tmp && sha256sum --ignore-missing --check /tmp/checksums.sha256) && \
    apt-get -y install "/tmp/${deb}" && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* "/tmp/${deb}" /tmp/checksums.sha256 && \
    ! ldd /usr/bin/Xkasmvnc | grep "not found" && \
    { /usr/bin/Xkasmvnc -version 2>&1 || true; } | grep -qi kasmvnc

# 3. Ghidra, with its JDK. Kali's package ships every module's help search index empty, so the
# help window fails to open ("IllegalArgumentException: view is invalid", What's New on first
# launch). GhidraHelpIndex.java builds the indexes with the package's own JavaHelp indexer, then
# fails the build unless every module's search view merges and a search finds topics. It skips
# modules that already have an index, so it does nothing once Kali fixes the package. It stays in
# the image for the smoke test, and to re-run after an in-workspace `apt upgrade` of ghidra.
COPY images/kali-desktop/GhidraHelpIndex.java /usr/local/lib/ghidra-help-index/GhidraHelpIndex.java
RUN apt-get update && \
    apt-get -y install ghidra && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    java -Djava.awt.headless=true \
      -cp "$(ls /usr/share/ghidra/Ghidra/Framework/Help/lib/javahelp-*.jar)" \
      /usr/local/lib/ghidra-help-index/GhidraHelpIndex.java /usr/share/ghidra

# 4-8. The security-lab toolset, one Kali tool group per layer: reverse engineering, forensics
# and crypto/stego, passwords, web, then exploitation with the static malware analysis and CTF
# extras (YARA, pefile, pwntools), where new tools go. Wine is not wanted, since it would let
# Windows samples run, but ollydbg (reverse engineering, forensics) and sqldict (web, passwords)
# depend on it.
RUN apt-get update && \
    apt-get -y install kali-tools-reverse-engineering && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN apt-get update && \
    apt-get -y install kali-tools-forensics kali-tools-crypto-stego && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN apt-get update && \
    apt-get -y install kali-tools-passwords && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN apt-get update && \
    apt-get -y install kali-tools-web && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN apt-get update && \
    apt-get -y install kali-tools-exploitation yara python3-pefile python3-pwntools && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

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
