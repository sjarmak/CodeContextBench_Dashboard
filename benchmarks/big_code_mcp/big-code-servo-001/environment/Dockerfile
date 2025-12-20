FROM rust:1.75-bullseye

WORKDIR /workspace

# Install dependencies including Node.js for Claude Code CLI
RUN apt-get update && apt-get install -y \
    git \
    curl \
    build-essential \
    python3 \
    python3-pip \
    nodejs \
    npm \
    cmake \
    pkg-config \
    libssl-dev \
    libfontconfig1-dev

# Install Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

# Initialize minimal Servo workspace structure
# Claude will use Sourcegraph MCP to understand the real codebase,
# so we just need a git repo with basic structure
RUN git init /workspace && \
    cd /workspace && \
    git config user.email "agent@example.com" && \
    git config user.name "Agent" && \
    mkdir -p components/script components/layout components/selectors \
             components/style scripts tests/wpt && \
    echo "# Servo (task environment)" > README.md && \
    git add . && \
    git commit -m "Initial workspace"

# Task setup complete
