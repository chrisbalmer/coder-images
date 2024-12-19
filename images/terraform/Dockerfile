FROM ghcr.io/chrisbalmer/coder-images-base:1.1.5

# Run everything as root
USER root

COPY /src/files.sha256 /tmp/

# Add hashicorp repo
RUN wget -O- https://apt.releases.hashicorp.com/gpg | \
    gpg --dearmor | \
    tee /usr/share/keyrings/hashicorp-archive-keyring.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] \
    https://apt.releases.hashicorp.com $(lsb_release -cs) main" | \
    tee /etc/apt/sources.list.d/hashicorp.list

# Install terraform and terragrunt
RUN apt update && \
    apt upgrade --yes && \
    apt install --yes \
      terraform && \
    cd /tmp/ && \
    curl -LO https://github.com/gruntwork-io/terragrunt/releases/download/v0.70.4/terragrunt_linux_amd64 && \
    sha256sum --ignore-missing --check /tmp/files.sha256 && \
    mv terragrunt_linux_amd64 /usr/local/bin/terragrunt && \
    chmod +x /usr/local/bin/terragrunt

# Install ansible
COPY /src/terraform-requirements.txt /tmp/requirements.txt
RUN pip3 install --upgrade pip && \
    pip3 install -r /tmp/requirements.txt

# Set back to coder user
USER coder
