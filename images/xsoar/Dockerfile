FROM ghcr.io/chrisbalmer/coder-images-base:0.0.3

# Run everything as root
USER root

# Install demisto-sdk
COPY requirements.txt /tmp/
RUN pip3 install --upgrade pip && \
    pip3 install -r /tmp/requirements.txt

# Set back to coder user
USER coder
