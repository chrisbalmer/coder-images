ARG BASE_IMAGE=ghcr.io/chrisbalmer/coder-images-base:latest
FROM ${BASE_IMAGE}

# Run everything as root
USER root

RUN apt update && \
    apt upgrade --yes && \
    apt install --yes \
      ubuntu-unity-desktop xfce4 libdatetime-perl dbus-x11 && \
    apt clean

# Set back to coder user
USER coder
