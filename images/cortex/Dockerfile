ARG BASE_IMAGE=ghcr.io/chrisbalmer/coder-images-base:latest
FROM ${BASE_IMAGE}

USER root

COPY /src/cortex-requirements.txt /tmp/requirements.txt

# Switch to coder user to own the venv
USER coder

# Create venv and install packages
RUN python3 -m venv /home/coder/.venv && \
    /home/coder/.venv/bin/pip install --upgrade pip && \
    /home/coder/.venv/bin/pip install -r /tmp/requirements.txt

# Put venv on PATH — works for all shells, survives dotfile replacement
ENV VIRTUAL_ENV=/home/coder/.venv
ENV PATH="/home/coder/.venv/bin:$PATH"
