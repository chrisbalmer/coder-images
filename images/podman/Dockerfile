FROM quay.io/podman/stable:v5.8.7

SHELL ["/bin/bash", "-c"]

# Fetch packages from dl.fedoraproject.org only. The stock repos use a metalink, which hands dnf
# a location-dependent list of third-party mirrors (some plain HTTP) that no egress allowlist can
# track; the build runners allow dl.fedoraproject.org. Cisco's OpenH264 codecs repo is not needed.
# The build fails if any repo still points at a mirror list.
RUN sed -i \
      -e 's|^#baseurl=http://download.example/pub/fedora/linux/|baseurl=https://dl.fedoraproject.org/pub/fedora/linux/|' \
      -e 's|^metalink=|#metalink=|' \
      /etc/yum.repos.d/fedora*.repo && \
    if [ -f /etc/yum.repos.d/fedora-cisco-openh264.repo ]; then \
      sed -i 's/^enabled=.*/enabled=0/' /etc/yum.repos.d/fedora-cisco-openh264.repo; \
    fi && \
    if grep -Hn '^\(metalink\|mirrorlist\)=' /etc/yum.repos.d/*.repo; then \
      echo "dnf would still use a mirror list" >&2; exit 1; \
    fi

# Per-image checksums: editing another image's checksums must not invalidate this build.
COPY images/podman/checksums.sha256 /tmp/checksums.sha256
# TARGETARCH picks the starship build: a multi-arch image must not ship x86_64 bytes on arm64.
ARG TARGETARCH
RUN dnf install -y git \
      patch \
      subversion \
      systemtap \
      diffstat \
      doxygen \
      patchutils \
      git-core \
      git-core-doc \
      kernel-devel \
      perl-Git \
      subversion-libs \
      systemtap-client \
      systemtap-devel \
      systemtap-runtime \
      apr \
      apr-util \
      dyninst \
      libdwarf \
      libserf \
      perl-Error \
      perl-TermReadKey \
      utf8proc \
      apr-util-openssl \
      zsh \
      jq \
      vim \
      sudo \
      unzip \
      wget \
      curl \
      python3 \
      python3-pip \
      curl \
      htop \
      man \
      bind-utils \
      rsync \
      fontconfig \
      iputils \
      ca-certificates && \
      sed -i 's/\/bin\/bash/\/usr\/bin\/zsh/g' /etc/passwd && \
    # Download fonts and starship then check hashes
    curl -LO https://github.com/ryanoasis/nerd-fonts/releases/download/v3.2.1/SourceCodePro.zip && \
    case "${TARGETARCH:-amd64}" in \
      amd64) STARSHIP_ARCH=x86_64 ;; \
      arm64) STARSHIP_ARCH=aarch64 ;; \
      *) echo "starship: unsupported TARGETARCH '${TARGETARCH}'" >&2; exit 1 ;; \
    esac && \
    curl -LO "https://github.com/starship/starship/releases/download/v1.19.0/starship-${STARSHIP_ARCH}-unknown-linux-musl.tar.gz" && \
    sha256sum --ignore-missing --check /tmp/checksums.sha256 && \
    # Install fonts
    unzip ./SourceCodePro.zip -d /usr/share/fonts && \
    fc-cache -v && \
    rm SourceCodePro.zip && \
    # Install starship
    tar xvf "starship-${STARSHIP_ARCH}-unknown-linux-musl.tar.gz" && \
    mv starship /usr/local/bin/ && \
    rm "starship-${STARSHIP_ARCH}-unknown-linux-musl.tar.gz"

# Add a user `coder` so that you're not developing as the `root` user
RUN userdel podman && \
    useradd coder \
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
ARG IMAGE_DESCRIPTION=Podman container runtime for Coder workspaces
LABEL org.opencontainers.image.title="coder-images-podman" \
      org.opencontainers.image.description="${IMAGE_DESCRIPTION}" \
      org.opencontainers.image.source="https://github.com/chrisbalmer/coder-images" \
      org.opencontainers.image.revision="${GIT_SHA}" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.created="${BUILD_CREATED}"
