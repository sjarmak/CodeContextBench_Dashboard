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
RUN git fetch origin a06141f73d603084910db381504b7c41eedb7210 2>/dev/null || true
RUN git checkout a06141f73d603084910db381504b7c41eedb7210 || git checkout -B fix a06141f73d603084910db381504b7c41eedb7210

# Install PyTorch build dependencies
RUN pip install -q numpy pyyaml mkl mkl-service setuptools cffi typing_extensions future six requests dataclasses

WORKDIR /workspace
