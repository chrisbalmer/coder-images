FROM ghcr.io/chrisbalmer/coder-images-base:0.0.1

# Run everything as root
USER root

# Install terraform and terragrunt
RUN wget -O- https://apt.releases.hashicorp.com/gpg | \
    gpg --dearmor | \
    sudo tee /usr/share/keyrings/hashicorp-archive-keyring.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] \
    https://apt.releases.hashicorp.com $(lsb_release -cs) main" | \
    sudo tee /etc/apt/sources.list.d/hashicorp.list && \
    apt update && \
    DEBIAN_FRONTEND="noninteractive" apt upgrade --yes && \
    DEBIAN_FRONTEND="noninteractive" apt install --yes \
    terraform && \
    cd /tmp/ && \
    curl -LO https://github.com/gruntwork-io/terragrunt/releases/download/v0.54.12/terragrunt_linux_amd64 && \
    mv terragrunt_linux_amd64 /usr/local/bin/terragrunt && \
    chmod +x /usr/local/bin/terragrunt

# Install ansible
COPY requirements.txt /tmp/
RUN pip3 install --upgrade pip && \
    pip3 install -r /tmp/requirements.txt

# Set back to coder user
USER coder
