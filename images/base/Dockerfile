FROM ubuntu:22.04

SHELL ["/bin/bash", "-c"]

COPY files.sha256 /tmp/
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
      dnsutils \
      jq \
      fontconfig \
      zsh && \
    # Install latest Git using their official PPA
    add-apt-repository ppa:git-core/ppa && \
    DEBIAN_FRONTEND="noninteractive" apt install --yes git && \
    apt clean && \
    sed -i 's/\/bin\/bash/\/usr\/bin\/zsh/g' /etc/passwd && \
    # Download fonts and starship then check hashes
    curl -LO https://github.com/ryanoasis/nerd-fonts/releases/download/v3.2.1/SourceCodePro.zip && \
    curl -LO https://github.com/starship/starship/releases/download/v1.19.0/starship-x86_64-unknown-linux-musl.tar.gz && \
    sha256sum --check /tmp/files.256
    # Install fonts
    unzip ./SourceCodePro.zip -d /usr/share/fonts && \
    fc-cache -v && \
    rm SourceCodePro.zip && \
    # Install starship
    tar xvf starship-x86_64-unknown-linux-musl.tar.gz && \
    mv starship /usr/local/bin/ && \
    rm starship-x86_64-unknown-linux-musl.tar.gz

# Set the locale
RUN sed -i 's/# \(en_US\.UTF-8 .*\)/\1/' /etc/locale.gen && \
    locale-gen
ENV LANG en_US.UTF-8  
ENV LANGUAGE en_US:en  
ENV LC_ALL en_US.UTF-8 

# Add a user `coder` so that you're not developing as the `root` user
RUN useradd coder \
      --create-home \
      --shell=/bin/bash \
      --uid=1000 \
      --user-group && \
    echo "coder ALL=(ALL) NOPASSWD:ALL" >>/etc/sudoers.d/nopasswd

USER coder