FROM golang:1.23-bullseye

WORKDIR /workspace

# Install dependencies including Node.js
RUN apt-get update && apt-get install -y \
    git \
    curl \
    build-essential \
    rsync \
    bash \
    make \
    nodejs \
    npm

# Install Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

# Clone Kubernetes repository at v1.30.0 tag
RUN git clone https://github.com/kubernetes/kubernetes.git /workspace && \
    cd /workspace && \
    git checkout v1.30.0 && \
    go mod download

# Task setup complete
