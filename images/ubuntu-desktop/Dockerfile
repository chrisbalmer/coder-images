ARG REGISTRY=ghcr.io
ARG IMAGE_OWNER=chrisbalmer
ARG BASE_TAG=latest
FROM ${REGISTRY}/${IMAGE_OWNER}/coder-images-base:${BASE_TAG}

# Run everything as root
USER root

RUN apt update && \
    apt upgrade --yes && \
    apt install --yes \
      ubuntu-unity-desktop xfce4 libdatetime-perl dbus-x11 && \
    apt clean

# Set back to coder user
USER coder
