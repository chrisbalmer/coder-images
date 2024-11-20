FROM ghcr.io/chrisbalmer/coder-images-base:1.1.4

# Run everything as root
USER root

RUN apt update && \
    DEBIAN_FRONTEND="noninteractive" apt upgrade --yes && \
    DEBIAN_FRONTEND="noninteractive" apt install --yes \
      ubuntu-unity-desktop xfce4 libdatetime-perl  dbus-x11

# Set back to coder user
USER coder
