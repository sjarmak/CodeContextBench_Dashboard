FROM node:22-bookworm

WORKDIR /workspace

# Install dependencies including Git, build tools, X11 dev libs
RUN apt-get update && apt-get install -y \
    git \
    curl \
    build-essential \
    python3 \
    python3-pip \
    libxkbfile-dev \
    libx11-dev \
    libxkbcommon-dev \
    pkg-config

# Install Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

# Clone VS Code repository at specific tag
# Don't do full npm install - just clone and let Claude handle it
RUN git clone https://github.com/microsoft/vscode.git /workspace && \
    cd /workspace && \
    git checkout 1.96.0

# Task setup complete
