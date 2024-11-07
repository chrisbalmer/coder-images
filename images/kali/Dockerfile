FROM kalilinux/kali-rolling:latest


# Install kali packages
ARG KALI_METAPACKAGE=core
ENV DEBIAN_FRONTEND noninteractive
RUN apt-get update
RUN apt-get -y upgrade
RUN apt-get -y install kali-linux-${KALI_METAPACKAGE}
RUN apt-get clean

# Install kali desktop
ARG KALI_DESKTOP=xfce
RUN apt-get -y install kali-desktop-${KALI_DESKTOP}
RUN apt-get -y install net-tools zsh vim curl libdatetime-perl

RUN useradd coder \
      --create-home \
      --shell=/usr/bin/zsh \
      --uid=1000 \
      --user-group && \
    echo "coder ALL=(ALL) NOPASSWD:ALL" >>/etc/sudoers.d/nopasswd

USER coder
