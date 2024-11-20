FROM ghcr.io/chrisbalmer/coder-images-base:1.1.4

# Run everything as root
USER root

# Install go
COPY /src/files.sha256 /tmp/
RUN curl -LO "https://go.dev/dl/go1.23.3.linux-amd64.tar.gz" && \
    sha256sum --ignore-missing --check /tmp/files.256 && \
    tar -C /usr/local -xzvf go1.22.5.linux-amd64.tar.gz && \
    rm go1.22.5.linux-amd64.tar.gz

RUN apt update && \
    apt install -y \
      mysql-client postgresql-client && \
    apt clean

# Setup go env vars
ENV GOROOT /usr/local/go
ENV PATH $PATH:$GOROOT/bin

ENV GOPATH /home/coder/go
ENV GOBIN $GOPATH/bin
ENV PATH $PATH:$GOBIN

# Set back to coder user
USER coder
RUN mkdir -p /home/coder/go/bin && \
    go install -v golang.org/x/tools/cmd/goimports@latest && \
    go install -v golang.org/x/tools/gopls@latest
