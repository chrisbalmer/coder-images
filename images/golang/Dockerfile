ARG BASE_IMAGE=ghcr.io/chrisbalmer/coder-images-base:latest
FROM ${BASE_IMAGE}

# Run everything as root
USER root

# Install go — TARGETARCH is set automatically by Docker for multi-platform builds
ARG TARGETARCH
COPY /src/files.sha256 /tmp/
RUN curl -LO "https://go.dev/dl/go1.26.0.linux-${TARGETARCH}.tar.gz" && \
    sha256sum --ignore-missing --check /tmp/files.sha256 && \
    tar -C /usr/local -xzvf go1.26.0.linux-${TARGETARCH}.tar.gz && \
    rm go1.26.0.linux-${TARGETARCH}.tar.gz

RUN apt-get update && \
    env && \
    apt-get install -y \
      mysql-client postgresql-client && \
    apt clean

# Setup go env vars
ENV GOROOT /usr/local/go
ENV PATH $PATH:$GOROOT/bin

# Setup temp GOPATH and GOBIN
ENV GOPATH=/opt/go
ENV GOBIN=$GOPATH/bin
ENV ORIGPATH=$PATH
ENV PATH=$PATH:$GOBIN

# Prep tools to copy to k8s volume
RUN mkdir -p /opt/go && \
    go install -v golang.org/x/tools/cmd/goimports@latest && \
    go install -v golang.org/x/tools/gopls@latest && \
    go install -v github.com/go-delve/delve/cmd/dlv@latest && \
    chown -R coder:coder /opt/go

# Set back to coder user
USER coder

# Fix go pathing
ENV GOPATH=/home/coder/go
ENV GOBIN=$GOPATH/bin
ENV PATH=$ORIGPATH:$GOBIN