FROM pytorch/pytorch:latest

WORKDIR /workspace

# Install additional build dependencies
RUN apt-get update && apt-get install -y \
    git \
    cmake \
    ninja-build \
    && rm -rf /var/lib/apt/lists/*

# Clone PyTorch repository at pre_fix_rev
RUN git clone https://github.com/pytorch/pytorch /workspace/src 2>/dev/null || true
WORKDIR /workspace/src
RUN git fetch origin 9976b77abbb6e920684f899c539101e4b412f911 2>/dev/null || true
RUN git checkout 9976b77abbb6e920684f899c539101e4b412f911 || git checkout -B fix 9976b77abbb6e920684f899c539101e4b412f911

# Install PyTorch build dependencies
RUN pip install -q numpy pyyaml mkl mkl-service setuptools cffi typing_extensions future six requests dataclasses

WORKDIR /workspace
