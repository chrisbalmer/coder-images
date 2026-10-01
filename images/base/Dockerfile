FROM ubuntu:26.04

SHELL ["/bin/bash", "-c"]

# Per-image checksums: editing another image's checksums must not invalidate this build.
COPY images/base/checksums.sha256 /tmp/checksums.sha256
ENV DEBIAN_FRONTEND=noninteractive

# Remove user `ubuntu` and add a user `coder`
RUN userdel ubuntu && \
    useradd coder \
      --create-home \
      --shell=/usr/bin/zsh \
      --uid=1000 \
      --user-group

# Install required tools
RUN apt update && \
    apt install -y curl gpg lsb-release software-properties-common && \
    apt clean

# Add 1Password Repo
RUN curl -sS https://downloads.1password.com/linux/keys/1password.asc | \
    gpg --dearmor --output /usr/share/keyrings/1password-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/1password-archive-keyring.gpg] https://downloads.1password.com/linux/debian/$(dpkg --print-architecture) stable main" | \
    tee /etc/apt/sources.list.d/1password.list && \
    mkdir -p /etc/debsig/policies/AC2D62742012EA22/ && \
    curl -sS https://downloads.1password.com/linux/debian/debsig/1password.pol | \
    tee /etc/debsig/policies/AC2D62742012EA22/1password.pol && \
    mkdir -p /usr/share/debsig/keyrings/AC2D62742012EA22 && \
    curl -sS https://downloads.1password.com/linux/keys/1password.asc | \
    gpg --dearmor --output /usr/share/debsig/keyrings/AC2D62742012EA22/debsig.gpg && \
    # Add Microsoft repo
    curl -sLS https://packages.microsoft.com/keys/microsoft.asc | \
    gpg --dearmor | tee /etc/apt/keyrings/microsoft.gpg > /dev/null && \
    chmod go+r /etc/apt/keyrings/microsoft.gpg && \
    AZ_DIST=$(lsb_release -cs) && \
    echo "Types: deb" > /etc/apt/sources.list.d/azure-cli.sources && \
    echo "URIs: https://packages.microsoft.com/repos/azure-cli/" >> /etc/apt/sources.list.d/azure-cli.sources && \
    echo "Suites: ${AZ_DIST}" >> /etc/apt/sources.list.d/azure-cli.sources && \
    echo "Components: main" >> /etc/apt/sources.list.d/azure-cli.sources && \
    echo "Architectures: $(dpkg --print-architecture)" >> /etc/apt/sources.list.d/azure-cli.sources && \
    echo "Signed-by: /etc/apt/keyrings/microsoft.gpg" >> /etc/apt/sources.list.d/azure-cli.sources && \
    # Add Git repo
    add-apt-repository ppa:git-core/ppa && \
    # Add NodeSource repo for Node.js 22.x LTS: its signing key and a signed-by source, the same
    # as the repos above, rather than running NodeSource's setup script unverified. The pin makes
    # apt prefer NodeSource's nodejs over Ubuntu's, which is what the setup script also writes.
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | \
    gpg --dearmor --output /etc/apt/keyrings/nodesource.gpg && \
    chmod go+r /etc/apt/keyrings/nodesource.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_22.x nodistro main" \
      > /etc/apt/sources.list.d/nodesource.list && \
    printf 'Package: nodejs\nPin: origin deb.nodesource.com\nPin-Priority: 600\n' \
      > /etc/apt/preferences.d/nodejs

# Install apps.
#
# The package refresh is opt-in. `apt upgrade` resolves against whatever the mirrors serve
# today, so an unconditional one changes this image's digest with no commit and invalidates
# cache-from for every dependent. A build without the flag still installs the newest packages
# available for the pinned list; it just does not rewrite the base's existing package set.
# Refresh it deliberately: Run workflow -> upgrade_base.
ARG APT_UPGRADE=false
RUN apt update && \
    if [ "$APT_UPGRADE" = "true" ]; then apt upgrade --yes; fi && \
    apt install --yes \
      1password-cli \
      azure-cli \
      bash \
      build-essential \
      ca-certificates \
      dnsutils \
      fd-find \
      fontconfig \
      git \
      htop \
      iputils-ping \
      jq \
      locales \
      nodejs \
      man \
      mysql-client \
      netcat-openbsd \
      postgresql-client \
      python3 \
      python3-pip \
      python3-venv \
      ripgrep \
      rsync \
      sudo \
      unzip \
      vim \
      wget \
      zsh && \
    apt clean

# TARGETARCH picks the starship build: a multi-arch image must not ship x86_64 bytes on arm64.
ARG TARGETARCH
# Change bash shells to zsh
RUN sed -i 's/\/bin\/bash/\/usr\/bin\/zsh/g' /etc/passwd && \
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
    rm "starship-${STARSHIP_ARCH}-unknown-linux-musl.tar.gz" && \
    # Allow coder user to use sudo without password
    echo "coder ALL=(ALL) NOPASSWD:ALL" >>/etc/sudoers.d/nopasswd

# Tools the workspace templates rely on: kubectl (startup scripts wait on in-namespace services
# and read their secrets), yq, uv (next to Python 3), and mc for S3-compatible object storage.
# The Postgres and MySQL clients come from apt above. gh, tea and fj are the GitHub, Gitea and
# Forgejo CLIs; tea and fj publish no checksum files, so their lines were recorded on download.
# gitea-mcp is the Gitea/Forgejo MCP server; the image only ships the binary, and whatever sets
# up the AI tools configures it. Each is pinned and must
# have a line in checksums.sha256: `--ignore-missing` alone would pass a file with no line, so
# the loop refuses one first. mc is archived upstream; this is its last release, and it gets no
# further fixes. ripgrep and fd come from apt above; Ubuntu installs fd as `fdfind`.
ARG KUBECTL_VERSION=v1.37.1
ARG YQ_VERSION=v4.53.6
ARG UV_VERSION=0.12.18
ARG MC_RELEASE=RELEASE.2025-08-13T08-35-41Z
ARG GH_VERSION=2.102.0
ARG TEA_VERSION=0.16.0
ARG FJ_VERSION=0.6.0
ARG GITEA_MCP_VERSION=1.8.0
RUN case "${TARGETARCH:-amd64}" in \
      amd64) ARCH=amd64; UV_ARCH=x86_64; GITEA_MCP_ARCH=x86_64 ;; \
      arm64) ARCH=arm64; UV_ARCH=aarch64; GITEA_MCP_ARCH=arm64 ;; \
      *) echo "tools: unsupported TARGETARCH '${TARGETARCH}'" >&2; exit 1 ;; \
    esac && \
    cd /tmp && \
    curl -fsSLo "kubectl-${ARCH}" "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/${ARCH}/kubectl" && \
    curl -fsSLO "https://github.com/mikefarah/yq/releases/download/${YQ_VERSION}/yq_linux_${ARCH}" && \
    curl -fsSLO "https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/uv-${UV_ARCH}-unknown-linux-gnu.tar.gz" && \
    curl -fsSLO "https://github.com/minio/mc/releases/download/${MC_RELEASE}/mc.linux-${ARCH}.${MC_RELEASE}" && \
    curl -fsSLO "https://github.com/cli/cli/releases/download/v${GH_VERSION}/gh_${GH_VERSION}_linux_${ARCH}.tar.gz" && \
    curl -fsSLO "https://gitea.com/gitea/tea/releases/download/v${TEA_VERSION}/tea-${TEA_VERSION}-linux-${ARCH}" && \
    curl -fsSLo "forgejo-cli-${FJ_VERSION}-${UV_ARCH}-linux.tar.gz" "https://codeberg.org/forgejo-contrib/forgejo-cli/releases/download/v${FJ_VERSION}/forgejo-cli-${UV_ARCH}-linux.tar.gz" && \
    curl -fsSLo "gitea-mcp-${GITEA_MCP_VERSION}-linux-${GITEA_MCP_ARCH}.tar.gz" "https://gitea.com/gitea/gitea-mcp/releases/download/v${GITEA_MCP_VERSION}/gitea-mcp_Linux_${GITEA_MCP_ARCH}.tar.gz" && \
    for f in "kubectl-${ARCH}" "yq_linux_${ARCH}" "uv-${UV_ARCH}-unknown-linux-gnu.tar.gz" "mc.linux-${ARCH}.${MC_RELEASE}" \
             "gh_${GH_VERSION}_linux_${ARCH}.tar.gz" "tea-${TEA_VERSION}-linux-${ARCH}" "forgejo-cli-${FJ_VERSION}-${UV_ARCH}-linux.tar.gz" \
             "gitea-mcp-${GITEA_MCP_VERSION}-linux-${GITEA_MCP_ARCH}.tar.gz"; do \
      grep -q "  ${f}\$" /tmp/checksums.sha256 || { echo "no checksum for ${f}" >&2; exit 1; }; \
    done && \
    sha256sum --ignore-missing --check /tmp/checksums.sha256 && \
    install -m 0755 "kubectl-${ARCH}" /usr/local/bin/kubectl && \
    install -m 0755 "yq_linux_${ARCH}" /usr/local/bin/yq && \
    tar xzf "uv-${UV_ARCH}-unknown-linux-gnu.tar.gz" && \
    install -m 0755 "uv-${UV_ARCH}-unknown-linux-gnu/uv" "uv-${UV_ARCH}-unknown-linux-gnu/uvx" /usr/local/bin/ && \
    install -m 0755 "mc.linux-${ARCH}.${MC_RELEASE}" /usr/local/bin/mc && \
    tar xzf "gh_${GH_VERSION}_linux_${ARCH}.tar.gz" && \
    install -m 0755 "gh_${GH_VERSION}_linux_${ARCH}/bin/gh" /usr/local/bin/gh && \
    install -m 0755 "tea-${TEA_VERSION}-linux-${ARCH}" /usr/local/bin/tea && \
    tar xzf "forgejo-cli-${FJ_VERSION}-${UV_ARCH}-linux.tar.gz" fj && \
    install -m 0755 fj /usr/local/bin/fj && \
    tar xzf "gitea-mcp-${GITEA_MCP_VERSION}-linux-${GITEA_MCP_ARCH}.tar.gz" gitea-mcp && \
    install -m 0755 gitea-mcp /usr/local/bin/gitea-mcp && \
    ln -s /usr/bin/fdfind /usr/local/bin/fd && \
    rm -rf kubectl-* yq_linux_* uv-* mc.linux-* gh_* tea-* forgejo-cli-* fj gitea-mcp* && \
    kubectl version --client && yq --version && uv --version && mc --version && fd --version && rg --version && \
    gh --version && tea --version && fj version && gitea-mcp -version && psql --version && mysql --version && \
    command -v nc

# Set the locale
RUN sed -i 's/# \(en_US\.UTF-8 .*\)/\1/' /etc/locale.gen && \
    locale-gen
ENV LANG=en_US.UTF-8  
ENV LANGUAGE=en_US:en  
ENV LC_ALL=en_US.UTF-8 

# Provenance. CI overwrites these; the defaults keep a local build honest.
# VERSION is namespaced with `ci/` so an untagged build can never masquerade as a release.
ARG VERSION=ci/dev
ARG GIT_SHA=unknown
ARG BUILD_CREATED=1970-01-01T00:00:00Z
ARG IMAGE_DESCRIPTION=Foundation image for Coder workspaces
LABEL org.opencontainers.image.title="coder-images-base" \
      org.opencontainers.image.description="${IMAGE_DESCRIPTION}" \
      org.opencontainers.image.source="https://github.com/chrisbalmer/coder-images" \
      org.opencontainers.image.revision="${GIT_SHA}" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.created="${BUILD_CREATED}"

USER coder
