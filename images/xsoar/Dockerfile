ARG BASE_IMAGE=ghcr.io/chrisbalmer/coder-images-base:latest
FROM ${BASE_IMAGE}

# Run everything as root
USER root

# Install demisto-sdk
COPY /src/xsoar-requirements.txt /tmp/requirements.txt
RUN pip3 install --upgrade pip && \
    pip3 install -r /tmp/requirements.txt

# Set back to coder user
USER coder
