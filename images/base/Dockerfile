FROM ubuntu:22.04

SHELL ["/bin/bash", "-c"]

# Install the Docker apt repository
RUN apt update && \
    DEBIAN_FRONTEND="noninteractive" apt upgrade --yes && \
    DEBIAN_FRONTEND="noninteractive" apt install --yes \
      bash \
      build-essential \
      ca-certificates \
      curl \
      htop \
      locales \
      man \
      python3 \
      python3-pip \
      software-properties-common \
      sudo \
      unzip \
      vim \
      wget \
      rsync && \
    # Install latest Git using their official PPA
    add-apt-repository ppa:git-core/ppa && \
    DEBIAN_FRONTEND="noninteractive" apt install --yes git && \
    apt clean

# Make typing unicode characters in the terminal work.
ENV LANG en_US.UTF-8

# Add a user `coder` so that you're not developing as the `root` user
RUN useradd coder \
      --create-home \
      --shell=/bin/bash \
      --uid=1000 \
      --user-group && \
    echo "coder ALL=(ALL) NOPASSWD:ALL" >>/etc/sudoers.d/nopasswd

USER coder