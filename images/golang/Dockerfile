FROM ghcr.io/chrisbalmer/coder-images-base:1.1.1

# Run everything as root
USER root

# Install go
COPY files.256 /tmp/
RUN curl -LO "https://go.dev/dl/go1.22.5.linux-amd64.tar.gz" && \
    sha256sum --check /tmp/files.256 && \
    tar -C /usr/local -xzvf go1.22.5.linux-amd64.tar.gz && \
    rm go1.22.5.linux-amd64.tar.gz

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
