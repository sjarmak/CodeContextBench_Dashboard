FROM ubuntu:22.04

# Prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update -qq && apt-get install -y -qq \
    git \
    curl \
    ca-certificates \
    build-essential \
    python3 \
    python3-pip \
    make \
    jq \
    && rm -rf /var/lib/apt/lists/*

# Copy 10Figure-Codebases repository (contains all 4 repos under src/)
# Pinned versions (cloned via build.sh with --depth 1):
#   - Kubernetes v1.29.3
#   - Django 5.0.4
#   - Envoy v1.29.2
#   - TensorFlow v2.16.1
COPY 10Figure-Codebases /10figure

# Install Python dependencies
WORKDIR /10figure
RUN if [ -f requirements.txt ]; then pip3 install --no-cache-dir -r requirements.txt; fi

# Validate all 4 repos are present under /10figure/src/
RUN test -d /10figure/src/kubernetes && \
    test -d /10figure/src/django && \
    test -d /10figure/src/envoy && \
    test -d /10figure/src/tensorflow && \
    echo "Validated: kubernetes/ django/ envoy/ tensorflow/ present under /10figure/src/"

# Create workspace directory
RUN mkdir -p /workspace

# Set working directory
WORKDIR /workspace

# Expose corpus path as env var
ENV CORPUS_ROOT=/10figure/src
ENV VALIDATOR_PATH=/10figure/scripts/validate_patch.py

# Default command
CMD ["/bin/bash"]
