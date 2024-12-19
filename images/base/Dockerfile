FROM ubuntu:22.04

SHELL ["/bin/bash", "-c"]

COPY /src/files.sha256 /tmp/
ENV DEBIAN_FRONTEND noninteractive

    # Install required tools
RUN apt update && \
    apt install -y curl gpg lsb-release software-properties-common && \
    apt clean

    # Add 1Password Repo
RUN curl -sS https://downloads.1password.com/linux/keys/1password.asc | \
    gpg --dearmor --output /usr/share/keyrings/1password-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/1password-archive-keyring.gpg] https://downloads.1password.com/linux/debian/$(dpkg --print-architecture) stable main" | \
    tee /etc/apt/sources.list.d/1password.list && \
    mkdir -p /etc/debsig/policies/AC2D62742012EA22/ && \
    curl -sS https://downloads.1password.com/linux/debian/debsig/1password.pol | \
    tee /etc/debsig/policies/AC2D62742012EA22/1password.pol && \
    mkdir -p /usr/share/debsig/keyrings/AC2D62742012EA22 && \
    curl -sS https://downloads.1password.com/linux/keys/1password.asc | \
    gpg --dearmor --output /usr/share/debsig/keyrings/AC2D62742012EA22/debsig.gpg && \
    # Add Microsoft repo
    curl -sLS https://packages.microsoft.com/keys/microsoft.asc | \
    gpg --dearmor | tee /etc/apt/keyrings/microsoft.gpg > /dev/null && \
    chmod go+r /etc/apt/keyrings/microsoft.gpg && \
    AZ_DIST=$(lsb_release -cs) && \
    echo "Types: deb" > /etc/apt/sources.list.d/azure-cli.sources && \
    echo "URIs: https://packages.microsoft.com/repos/azure-cli/" >> /etc/apt/sources.list.d/azure-cli.sources && \
    echo "Suites: ${AZ_DIST}" >> /etc/apt/sources.list.d/azure-cli.sources && \
    echo "Components: main" >> /etc/apt/sources.list.d/azure-cli.sources && \
    echo "Architectures: $(dpkg --print-architecture)" >> /etc/apt/sources.list.d/azure-cli.sources && \
    echo "Signed-by: /etc/apt/keyrings/microsoft.gpg" >> /etc/apt/sources.list.d/azure-cli.sources && \
    # Add Git repo
    add-apt-repository ppa:git-core/ppa

    # Install apps
RUN apt update && \
    apt upgrade --yes && \
    apt install --yes \
      1password-cli \
      azure-cli \
      bash \
      build-essential \
      ca-certificates \
      dnsutils \
      fontconfig \
      git \
      htop \
      iputils-ping \
      jq \
      locales \
      man \
      python3 \
      python3-pip \
      rsync \
      sudo \
      unzip \
      vim \
      wget \
      zsh && \
    apt clean

    # Change bash shells to zsh
RUN sed -i 's/\/bin\/bash/\/usr\/bin\/zsh/g' /etc/passwd && \
    # Download fonts and starship then check hashes
    curl -LO https://github.com/ryanoasis/nerd-fonts/releases/download/v3.2.1/SourceCodePro.zip && \
    curl -LO https://github.com/starship/starship/releases/download/v1.19.0/starship-x86_64-unknown-linux-musl.tar.gz && \
    sha256sum --ignore-missing --check /tmp/files.sha256 && \
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
      --shell=/usr/bin/zsh \
      --uid=1000 \
      --user-group && \
    echo "coder ALL=(ALL) NOPASSWD:ALL" >>/etc/sudoers.d/nopasswd

USER coder
