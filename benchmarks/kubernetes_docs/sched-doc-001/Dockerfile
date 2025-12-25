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
RUN git clone --depth 1 https://github.com/kubernetes/kubernetes.git . && \
    git config user.email "agent@example.com" && \
    git config user.name "Agent"

# Strip documentation for the target package (surgical strip)
RUN find pkg/scheduler/framework/plugins/podtopologyspread -name "doc.go" -delete
RUN find pkg/scheduler/framework/plugins/podtopologyspread -name "README.md" -delete
RUN find pkg/scheduler/framework/plugins/podtopologyspread -name "*.go" -exec sed -i '/^\/\* Package/d' {} +

# Create a place for the agent to write the result
RUN mkdir -p pkg/scheduler/framework/plugins/podtopologyspread
