FROM node:22-bookworm

WORKDIR /workspace

# Install dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    build-essential \
    python3 \
    python3-pip

# Install Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

# Initialize minimal VS Code workspace structure
# Claude will use Sourcegraph MCP to understand the real codebase,
# so we just need a git repo with basic structure
RUN git init /workspace && \
    cd /workspace && \
    git config user.email "agent@example.com" && \
    git config user.name "Agent" && \
    mkdir -p src/editor src/browser src/vs && \
    echo "# VS Code (task environment)" > README.md && \
    echo '{"version": "1.96.0"}' > package.json && \
    git add . && \
    git commit -m "Initial workspace"

# Task setup complete
