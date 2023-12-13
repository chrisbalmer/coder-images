FROM ghcr.io/chrisbalmer/coder-images-base:latest

# Run everything as root
USER root

# Install go
RUN curl -L "https://go.dev/dl/go1.21.5.linux-amd64.tar.gz" && \
    sha256sum --check "e2bc0b3e4b64111ec117295c088bde5f00eeed1567999ff77bc859d7df70078e" && \
    tar -C /usr/local -xzvf go1.21.5.linux-amd64.tar.gz && \
    rm go1.21.5.linux-amd64.tar.gz && \
    mkdir -p /home/coder/go/bin

# Setup go env vars
ENV GOROOT /usr/local/go
ENV PATH $PATH:$GOROOT/bin

ENV GOPATH /home/coder/go
ENV GOBIN $GOPATH/bin
ENV PATH $PATH:$GOBIN

# Set back to coder user
USER coder