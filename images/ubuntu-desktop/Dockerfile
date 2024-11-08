FROM ghcr.io/chrisbalmer/coder-images-base:1.1.3

# Run everything as root
USER root

RUN apt update && \
    DEBIAN_FRONTEND="noninteractive" apt upgrade --yes && \
    DEBIAN_FRONTEND="noninteractive" apt install --yes \
      ubuntu-unity-desktop

# Set back to coder user
USER coder
