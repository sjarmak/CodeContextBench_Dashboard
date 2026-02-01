# Multi-stage build for harbor-10figure:base
# Stage 1: Prepare source trees (strip .git, unnecessary files)
# Stage 2: Runtime image with only source + tools

# --- Build stage: strip .git metadata and non-essential files ---
FROM ubuntu:22.04 AS builder

COPY 10Figure-Codebases /10figure-raw

# Strip .git directories to reduce image size (~195MB savings)
RUN find /10figure-raw/src -name ".git" -type d -exec rm -rf {} + 2>/dev/null || true

# Prepare clean source tree with only the 4 target repos
RUN mkdir -p /10figure/src && \
    cp -r /10figure-raw/src/kubernetes /10figure/src/kubernetes && \
    cp -r /10figure-raw/src/envoy /10figure/src/envoy && \
    cp -r /10figure-raw/src/django /10figure/src/django && \
    cp -r /10figure-raw/src/tensorflow /10figure/src/tensorflow

# Copy scripts, scoring, and config files
RUN cp -r /10figure-raw/scripts /10figure/scripts && \
    cp -r /10figure-raw/scoring /10figure/scoring 2>/dev/null || true && \
    cp -r /10figure-raw/tasks /10figure/tasks 2>/dev/null || true && \
    cp /10figure-raw/requirements.txt /10figure/requirements.txt 2>/dev/null || true

# --- Runtime stage: minimal image with source + tools ---
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

# Copy prepared source trees from builder
COPY --from=builder /10figure /10figure

# Install Python dependencies
WORKDIR /10figure
RUN if [ -f requirements.txt ]; then pip3 install --no-cache-dir -r requirements.txt; fi

# Validate corpus structure - all 4 repos must be present
RUN test -d /10figure/src/kubernetes && \
    test -d /10figure/src/envoy && \
    test -d /10figure/src/django && \
    test -d /10figure/src/tensorflow && \
    echo "Corpus validated: kubernetes envoy django tensorflow"

# Validate scoring/validator script
RUN test -f /10figure/scripts/validate_patch.py && \
    echo "Validator script present"

# Create workspace directory
RUN mkdir -p /workspace

# Set working directory
WORKDIR /workspace

# Pinned commit SHAs (for documentation; repos checked out at these commits)
ENV CORPUS_ROOT=/10figure/src
ENV VALIDATOR_PATH=/10figure/scripts/validate_patch.py
ENV KUBERNETES_SHA=ef274e869c3ea3d4042fada38a56221283a42362
ENV ENVOY_SHA=782c6caee166a8414097f548f7309114863379a8
ENV DJANGO_SHA=c4e07f94ebc1f9eaa3dae7b3dc6a2b9832182a10
ENV TENSORFLOW_SHA=420baf67d8c9fce3b66e435e7a4fdec57ecf4122

# Default command
CMD ["/bin/bash"]
