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

# Initialize minimal Kubernetes workspace structure
# Claude will use Sourcegraph MCP to understand the real codebase,
# so we just need a git repo with basic structure
RUN git init /workspace && \
    cd /workspace && \
    git config user.email "agent@example.com" && \
    git config user.name "Agent" && \
    mkdir -p pkg/kubelet pkg/scheduler pkg/controller-manager cmd && \
    echo "# Kubernetes (task environment)" > README.md && \
    git add . && \
    git commit -m "Initial workspace"

# Task setup complete
