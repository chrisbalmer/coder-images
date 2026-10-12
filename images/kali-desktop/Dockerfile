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
# session), so a lock screen locks the user out of their own desktop. Kali's kali-desktop-xfce is
# a protected package that depends on xfce4-screensaver, so the locker stays installed, but its
# daemon is diverted away (dpkg-divert survives upgrades): the session autostart, D-Bus
# activation (org.xfce.ScreenSaver) and xflock4 all find nothing to run. That beats configuring
# it off, which a setting in a persistent home could undo. An apt pin keeps the other lockers
# out of later installs. KasmVNC needs nothing else: its X server ignores screen blanking and
# DPMS, and its idle timeouts default to never.
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
    dpkg-divert --local --rename --divert /usr/bin/xfce4-screensaver.disabled \
      --add /usr/bin/xfce4-screensaver && \
    printf 'Package: light-locker xscreensaver mate-screensaver gnome-screensaver\nPin: version *\nPin-Priority: -1\n' \
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

# 9-14. Reverse-engineering extras, for the desktop and for headless use over SSH, where an MCP
# client drives Ghidra (ghidra-mcp) and gdb. Nothing here goes under /home/coder: the venv is in
# /opt/venvs/re, .NET in /usr/share/dotnet, its tools in /opt/dotnet-tools, and the shell setup
# in /etc. These layers come after the user so the venv can belong to coder, as cortex's does.

# 9. Tracing, eBPF, TLS netcat, GEF for gdb, keystone's Python bindings, and the compilers that
# pycdc and JPype (pyghidra's Java bridge, which has no wheel for Kali's Python) build with.
# .NET needs ICU, which libicu-dev pulls in at whatever version the distribution is on.
RUN apt-get update && \
    apt-get -y install \
      ltrace strace gdb gef bpftool llvm ncat \
      python3-venv python3-dev python3-keystone-engine \
      build-essential cmake libicu-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 10. pycdc and pycdas, the Python bytecode decompiler and disassembler. Kali doesn't package
# them and upstream doesn't tag releases, so the build pins a commit; fetching by hash makes the
# commit its own checksum.
ARG PYCDC_COMMIT=b4289760970dbc399684f1e155ec6d1ea1cc787e
RUN git init -q /tmp/pycdc && \
    git -C /tmp/pycdc fetch -q --depth 1 https://github.com/zrax/pycdc.git "${PYCDC_COMMIT}" && \
    git -C /tmp/pycdc checkout -q FETCH_HEAD && \
    cmake -S /tmp/pycdc -B /tmp/pycdc/build -DCMAKE_BUILD_TYPE=Release && \
    cmake --build /tmp/pycdc/build -j"$(nproc)" && \
    cmake --install /tmp/pycdc/build --prefix /usr/local && \
    rm -rf /tmp/pycdc && \
    pycdc --help 2>/dev/null && test -x /usr/local/bin/pycdas

# 11. uv, the same release base ships. Each download must have a line in checksums.sha256.
ARG UV_VERSION=0.12.18
COPY images/kali-desktop/checksums.sha256 /tmp/checksums.sha256
RUN case "${TARGETARCH:-amd64}" in \
      amd64) UV_ARCH=x86_64 ;; \
      arm64) UV_ARCH=aarch64 ;; \
    esac && \
    f="uv-${UV_ARCH}-unknown-linux-gnu.tar.gz" && \
    curl -fsSL -o "/tmp/${f}" "https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/${f}" && \
    { grep -q "  ${f}\$" /tmp/checksums.sha256 || { echo "no checksum for ${f}" >&2; exit 1; }; } && \
    (cd /tmp && sha256sum --ignore-missing --check /tmp/checksums.sha256) && \
    tar -xzf "/tmp/${f}" -C /tmp && \
    install -m 0755 "/tmp/uv-${UV_ARCH}-unknown-linux-gnu/uv" "/tmp/uv-${UV_ARCH}-unknown-linux-gnu/uvx" /usr/local/bin/ && \
    rm -rf /tmp/uv-* && \
    uv --version

# 12. The .NET SDK (the current LTS) and ilspycmd, the ILSpy decompiler's command line. The SDK
# goes in /usr/share/dotnet, where a .NET app looks by default, and the tool in a tool path
# rather than a user's ~/.dotnet/tools. The first-run files and the NuGet cache go to /tmp and
# are removed.
ARG DOTNET_SDK_VERSION=10.0.401
ARG ILSPYCMD_VERSION=11.1.0.9782
ENV DOTNET_ROOT=/usr/share/dotnet \
    DOTNET_CLI_TELEMETRY_OPTOUT=1 \
    DOTNET_NOLOGO=1
RUN case "${TARGETARCH:-amd64}" in \
      amd64) RID=x64 ;; \
      arm64) RID=arm64 ;; \
    esac && \
    f="dotnet-sdk-${DOTNET_SDK_VERSION}-linux-${RID}.tar.gz" && \
    curl -fsSL -o "/tmp/${f}" "https://builds.dotnet.microsoft.com/dotnet/Sdk/${DOTNET_SDK_VERSION}/${f}" && \
    { grep -q "  ${f}\$" /tmp/checksums.sha256 || { echo "no checksum for ${f}" >&2; exit 1; }; } && \
    (cd /tmp && sha256sum --ignore-missing --check /tmp/checksums.sha256) && \
    install -d /usr/share/dotnet && \
    tar -xzf "/tmp/${f}" -C /usr/share/dotnet && \
    rm -f "/tmp/${f}" /tmp/checksums.sha256 && \
    ln -s /usr/share/dotnet/dotnet /usr/local/bin/dotnet && \
    install -d /etc/dotnet && echo /usr/share/dotnet > /etc/dotnet/install_location && \
    DOTNET_CLI_HOME=/tmp/dotnet-home NUGET_PACKAGES=/tmp/nuget \
      dotnet tool install --tool-path /opt/dotnet-tools ilspycmd --version "${ILSPYCMD_VERSION}" && \
    rm -rf /tmp/dotnet-home /tmp/nuget /tmp/NuGetScratch* && \
    DOTNET_CLI_HOME=/tmp/dotnet-home /opt/dotnet-tools/ilspycmd --version && \
    rm -rf /tmp/dotnet-home

# 13. The Python environment for binary analysis: angr, z3, pyghidra, pyghidra-mcp and
# pyinstxtractor-ng, pinned in src/kali-desktop/requirements.txt. It sees the system site
# packages, so Kali's pwntools, capstone, unicorn and keystone stay importable and angr reuses
# the capstone it pins when Kali's matches. It belongs to coder, so `uv pip install` into it works
# without sudo (until the next restart: the root filesystem doesn't persist).
COPY src/kali-desktop/requirements.txt /tmp/re-requirements.txt
RUN install -d -o coder -g coder /opt/venvs/re
USER coder
# No uv cache: as coder it would land under /home/coder, which a workspace's home volume hides.
RUN export UV_NO_CACHE=1 UV_PYTHON_DOWNLOADS=never && \
    uv venv --seed --system-site-packages --python /usr/bin/python3 /opt/venvs/re && \
    uv pip install --python /opt/venvs/re/bin/python -r /tmp/re-requirements.txt && \
    PWNLIB_NOTERM=1 /opt/venvs/re/bin/python -c \
      "import angr, z3, pyghidra, pwn, unicorn, keystone, capstone, pyinstxtractor_ng" && \
    /opt/venvs/re/bin/pyghidra-mcp --version
USER root
RUN rm -f /tmp/re-requirements.txt

# 14. Shell setup and helper scripts, last because they change most often:
#   /etc/profile.d/re-tools.sh      PATH, GHIDRA_INSTALL_DIR, DOTNET_ROOT, and TERM when unset
#   /etc/gdb/gdbinit.d/gef.gdb      loads GEF into every gdb (GEF_DISABLE=1 for plain gdb)
#   /usr/local/bin/gef              Kali's `gef` command, minus the second load of GEF
#   /usr/local/bin/analyzeHeadless  Ghidra's headless analyzer, on the PATH
#   /usr/local/bin/ghidra-mcp       pyghidra-mcp over stdio, safe to start again
#   /usr/local/bin/re-check-tools   checks the whole toolset from a user's shell
# Debian's /etc/profile resets PATH in every login shell (Kali's zprofile reads it), so the ENV
# below doesn't reach one alone; profile.d puts the paths back. zsh reads zshenv in every
# session, login or not, including a command run over SSH, and interactive bash reads
# bash.bashrc. The ENV covers processes no shell starts.
COPY images/kali-desktop/rootfs/ /
RUN printf '%s\n' '' \
      '# Paths and settings for the reverse-engineering tools, in every zsh (coder-images).' \
      'if [ -r /etc/profile.d/re-tools.sh ]; then emulate sh -c ". /etc/profile.d/re-tools.sh"; fi' \
      >> /etc/zsh/zshenv && \
    printf '%s\n' '' \
      '# Paths and settings for the reverse-engineering tools (coder-images).' \
      'if [ -r /etc/profile.d/re-tools.sh ]; then . /etc/profile.d/re-tools.sh; fi' \
      >> /etc/bash.bashrc && \
    chmod 0755 /usr/local/bin/gef /usr/local/bin/analyzeHeadless /usr/local/bin/ghidra-mcp \
      /usr/local/bin/re-check-tools && \
    chmod 0644 /etc/profile.d/re-tools.sh /etc/gdb/gdbinit.d/gef.gdb
ENV GHIDRA_INSTALL_DIR=/usr/share/ghidra \
    VIRTUAL_ENV=/opt/venvs/re \
    PATH="/opt/venvs/re/bin:/opt/dotnet-tools:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

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
