FROM quay.io/podman/stable:v5.2.2

SHELL ["/bin/bash", "-c"]

COPY /src/files.sha256 /tmp/
RUN dnf install -y git \
      patch \
      subversion \
      systemtap \
      diffstat \
      doxygen \
      patchutils \
      git-core \
      git-core-doc \
      kernel-devel \
      perl-Git \
      subversion-libs \
      systemtap-client \
      systemtap-devel \
      systemtap-runtime \
      apr \
      apr-util \
      dyninst \
      libdwarf \
      libserf \
      perl-Error \
      perl-TermReadKey \
      utf8proc \
      apr-util-openssl \
      zsh \
      jq \
      vim \
      sudo \
      unzip \
      wget \
      curl \
      python3 \
      python3-pip \
      curl \
      htop \
      man \
      bind-utils \
      rsync \
      fontconfig \
      iputils \
      ca-certificates && \
      sed -i 's/\/bin\/bash/\/usr\/bin\/zsh/g' /etc/passwd && \
    # Download fonts and starship then check hashes
    curl -LO https://github.com/ryanoasis/nerd-fonts/releases/download/v3.2.1/SourceCodePro.zip && \
    curl -LO https://github.com/starship/starship/releases/download/v1.19.0/starship-x86_64-unknown-linux-musl.tar.gz && \
    sha256sum --check /tmp/files.sha256 && \
    # Install fonts
    unzip ./SourceCodePro.zip -d /usr/share/fonts && \
    fc-cache -v && \
    rm SourceCodePro.zip && \
    # Install starship
    tar xvf starship-x86_64-unknown-linux-musl.tar.gz && \
    mv starship /usr/local/bin/ && \
    rm starship-x86_64-unknown-linux-musl.tar.gz

# Add a user `coder` so that you're not developing as the `root` user
RUN useradd coder \
      --create-home \
      --shell=/usr/bin/zsh \
      --user-group && \
    echo "coder ALL=(ALL) NOPASSWD:ALL" >>/etc/sudoers.d/nopasswd

USER coder
