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

COPY images/infra/checksums.sha256 /tmp/checksums.sha256

# Release assets are named by Go's GOARCH, which matches Docker's TARGETARCH for amd64 and arm64.
# An unsupported TARGETARCH fails the build instead of downloading amd64 bytes into another
# architecture's layer.
ARG TARGETARCH

# Add hashicorp repo
RUN wget -O- https://apt.releases.hashicorp.com/gpg | \
    gpg --dearmor | \
    tee /usr/share/keyrings/hashicorp-archive-keyring.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] \
    https://apt.releases.hashicorp.com $(lsb_release -cs) main" | \
    tee /etc/apt/sources.list.d/hashicorp.list

# Terraform comes from HashiCorp's signed apt repository, pinned to one version.
# No `apt upgrade`: this image inherits a patched base, and upgrading again would make the
# layer depend on the mirror's state at build time instead of on this commit.
ARG TERRAFORM_VERSION=1.16.4
RUN apt update && \
    apt install --yes \
      "terraform=${TERRAFORM_VERSION}-1" && \
    apt clean

# Cluster tools, each pinned and checked against checksums.sha256 (a file with no line there
# is refused first: `--ignore-missing` alone would pass it). flux and talosctl are
# recent releases (pin them to your cluster's versions if they differ); cilium-cli 0.20 supports Cilium 1.17 and newer. kubectl comes from base.
ARG TERRAGRUNT_VERSION=v1.1.6
ARG HELM_VERSION=v3.22.0
ARG KUSTOMIZE_VERSION=v5.8.1
ARG FLUX_VERSION=2.7.5
ARG TALOS_VERSION=v1.13.8
ARG CILIUM_CLI_VERSION=v0.20.1
ARG KUBECONFORM_VERSION=v0.8.0
RUN case "${TARGETARCH:-amd64}" in \
      amd64|arm64) ARCH="${TARGETARCH:-amd64}" ;; \
      *) echo "tools: unsupported TARGETARCH '${TARGETARCH}'" >&2; exit 1 ;; \
    esac && \
    mkdir /tmp/tools && cd /tmp/tools && \
    curl -fsSLO "https://github.com/gruntwork-io/terragrunt/releases/download/${TERRAGRUNT_VERSION}/terragrunt_linux_${ARCH}" && \
    curl -fsSLO "https://get.helm.sh/helm-${HELM_VERSION}-linux-${ARCH}.tar.gz" && \
    curl -fsSLO "https://github.com/kubernetes-sigs/kustomize/releases/download/kustomize%2F${KUSTOMIZE_VERSION}/kustomize_${KUSTOMIZE_VERSION}_linux_${ARCH}.tar.gz" && \
    curl -fsSLO "https://github.com/fluxcd/flux2/releases/download/v${FLUX_VERSION}/flux_${FLUX_VERSION}_linux_${ARCH}.tar.gz" && \
    curl -fsSLO "https://github.com/siderolabs/talos/releases/download/${TALOS_VERSION}/talosctl-linux-${ARCH}" && \
    curl -fsSLO "https://github.com/cilium/cilium-cli/releases/download/${CILIUM_CLI_VERSION}/cilium-linux-${ARCH}.tar.gz" && \
    curl -fsSLO "https://github.com/yannh/kubeconform/releases/download/${KUBECONFORM_VERSION}/kubeconform-linux-${ARCH}.tar.gz" && \
    for f in *; do \
      grep -q "  ${f}\$" /tmp/checksums.sha256 || { echo "no checksum for ${f}" >&2; exit 1; }; \
    done && \
    sha256sum --ignore-missing --check /tmp/checksums.sha256 && \
    install -m 0755 "terragrunt_linux_${ARCH}" /usr/local/bin/terragrunt && \
    install -m 0755 "talosctl-linux-${ARCH}" /usr/local/bin/talosctl && \
    tar xzf "helm-${HELM_VERSION}-linux-${ARCH}.tar.gz" "linux-${ARCH}/helm" && \
    tar xzf "kustomize_${KUSTOMIZE_VERSION}_linux_${ARCH}.tar.gz" kustomize && \
    tar xzf "flux_${FLUX_VERSION}_linux_${ARCH}.tar.gz" flux && \
    tar xzf "cilium-linux-${ARCH}.tar.gz" cilium && \
    tar xzf "kubeconform-linux-${ARCH}.tar.gz" kubeconform && \
    install -m 0755 "linux-${ARCH}/helm" kustomize flux cilium kubeconform /usr/local/bin/ && \
    cd / && rm -rf /tmp/tools

# Install ansible. The venv lives outside /home/coder: a workspace mounts its persistent home
# volume there, and a Kubernetes volume is not seeded from the image, so anything installed under
# it disappears. It is owned by coder, so `pip install` into it still works without sudo.
COPY src/infra/requirements.txt /tmp/requirements.txt
RUN install -d -o coder -g coder /opt/venvs/infra

# Set back to coder user
USER coder

RUN python3 -m venv /opt/venvs/infra && \
    /opt/venvs/infra/bin/pip install --no-cache-dir --upgrade pip && \
    /opt/venvs/infra/bin/pip install --no-cache-dir -r /tmp/requirements.txt

ENV VIRTUAL_ENV=/opt/venvs/infra
ENV PATH="/opt/venvs/infra/bin:$PATH"

# Smoke test: every tool runs as the workspace user (uid 1000, no sudo), on each architecture
# built, so a binary for the wrong architecture or one that needs root fails the build.
RUN test "$(id -u):$(id -g)" = 1000:1000 && \
    terraform version && \
    terragrunt --version && \
    ansible --version && \
    helm version --short && \
    kustomize version && \
    flux --version && \
    talosctl version --client --short && \
    cilium version --client && \
    kubeconform -v && \
    kubectl version --client

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
ARG IMAGE_DESCRIPTION=Infrastructure tools: Terraform, Terragrunt, Ansible, Helm, Flux, Talos and Cilium CLIs
LABEL org.opencontainers.image.title="coder-images-infra" \
      org.opencontainers.image.description="${IMAGE_DESCRIPTION}" \
      org.opencontainers.image.base.name="${BASE_NAME}:${BASE_VERSION}" \
      org.opencontainers.image.base.digest="${BASE_DIGEST}" \
      org.opencontainers.image.source="https://github.com/chrisbalmer/coder-images" \
      org.opencontainers.image.revision="${GIT_SHA}" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.created="${BUILD_CREATED}"
