FROM golang:1.23-bookworm

WORKDIR /workspace

# Install dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    python3 \
    npm \
    ripgrep

# Clone the actual Kubernetes repository
# This ensures BOTH baseline and MCP agents have identical file access
RUN git clone --depth 1 https://github.com/kubernetes/kubernetes.git . && \
    git config user.email "agent@example.com" && \
    git config user.name "Agent"

# Strip documentation for the target package (surgical strip)
# 1. Remove doc.go
RUN find pkg/kubelet/cm -name "doc.go" -delete
# 2. Remove README.md
RUN find pkg/kubelet/cm -name "README.md" -delete
# 3. Strip package comments from Go files
RUN find pkg/kubelet/cm -name "*.go" -exec sed -i '/^\/\/ Package/d' {} +

# Create a place for the agent to write the result
RUN mkdir -p pkg/kubelet/cm

# Ensure the agent can run tests if needed (though not required for this task)
# The evaluation will be done via LLM judge on the produced doc.go
