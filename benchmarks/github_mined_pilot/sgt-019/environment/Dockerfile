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
RUN git fetch origin cbe1a35dbdfdc9b7490212bdd812f3e2f4ce9e2d 2>/dev/null || true
RUN git checkout cbe1a35dbdfdc9b7490212bdd812f3e2f4ce9e2d || git checkout -B fix cbe1a35dbdfdc9b7490212bdd812f3e2f4ce9e2d

# Install PyTorch build dependencies
RUN pip install -q numpy pyyaml mkl mkl-service setuptools cffi typing_extensions future six requests dataclasses

WORKDIR /workspace
