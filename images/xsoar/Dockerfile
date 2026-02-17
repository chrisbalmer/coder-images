ARG REGISTRY=ghcr.io
ARG IMAGE_OWNER=chrisbalmer
ARG BASE_TAG=latest
FROM ${REGISTRY}/${IMAGE_OWNER}/coder-images-base:${BASE_TAG}

# Run everything as root
USER root

# Install demisto-sdk
COPY /src/xsoar-requirements.txt /tmp/requirements.txt
RUN pip3 install --upgrade pip && \
    pip3 install -r /tmp/requirements.txt

# Set back to coder user
USER coder
