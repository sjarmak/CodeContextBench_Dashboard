FROM nvidia/cuda:12.1.0-devel-ubuntu22.04

WORKDIR /workspace

# Install Python and dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    git \
    curl \
    build-essential \
    cmake \
    nodejs \
    npm

# Install Python build tools
RUN pip3 install --upgrade pip setuptools wheel

# Install Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

# Initialize minimal TensorRT-LLM workspace structure
# Claude will use Sourcegraph MCP to understand the real codebase,
# so we just need a git repo with basic structure
RUN git init /workspace && \
    cd /workspace && \
    git config user.email "agent@example.com" && \
    git config user.name "Agent" && \
    mkdir -p tensorrt_llm tensorrt_llm/models tensorrt_llm/models/llama \
             tensorrt_llm/quantization cpp tests && \
    echo "# TensorRT-LLM (task environment)" > README.md && \
    echo '{"name": "tensorrt_llm"}' > setup.py && \
    git add . && \
    git commit -m "Initial workspace"

# Task setup complete
