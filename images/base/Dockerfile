FROM ubuntu:22.04

SHELL ["/bin/bash", "-c"]

# Declare Enviorment Variables
ENV LANG='en_US.UTF-8' \
    LC_ALL='en_US.UTF-8'

# Set up the locale and make sure the system uses unicode for the file system.
RUN DEBIAN_FRONTEND="noninteractive" apt -y update && \
    DEBIAN_FRONTEND="noninteractive" apt -y install locales && \
    sed -i -e 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen && \
    dpkg-reconfigure locales && \
    update-locale LANG=en_US.UTF-8

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
      iputils-ping \
      rsync \
      dnsutils && \
    # Install latest Git using their official PPA
    add-apt-repository ppa:git-core/ppa && \
    DEBIAN_FRONTEND="noninteractive" apt install --yes git && \
    apt clean

# Add a user `coder` so that you're not developing as the `root` user
RUN useradd coder \
      --create-home \
      --shell=/bin/bash \
      --uid=1000 \
      --user-group && \
    echo "coder ALL=(ALL) NOPASSWD:ALL" >>/etc/sudoers.d/nopasswd

USER coder