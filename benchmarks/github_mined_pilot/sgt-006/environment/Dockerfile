FROM pytorch/pytorch:2.1-runtime-cuda12.1-cudnn8-devel

WORKDIR /workspace

# Install additional build dependencies
RUN apt-get update && apt-get install -y \
    git \
    cmake \
    ninja-build \
    && rm -rf /var/lib/apt/lists/*

# Clone PyTorch repository at pre_fix_rev
RUN git clone --depth 1 https://github.com/pytorch/pytorch /src 2>/dev/null || git clone https://github.com/pytorch/pytorch /src
WORKDIR /src
RUN git fetch origin a61b434dd46e951240ca6b9dd0e975f281c6d2a2 2>/dev/null || true
RUN git checkout a61b434dd46e951240ca6b9dd0e975f281c6d2a2 || git checkout -B fix a61b434dd46e951240ca6b9dd0e975f281c6d2a2

# Install PyTorch build dependencies
RUN pip install -q numpy pyyaml mkl mkl-service setuptools cffi typing_extensions future six requests dataclasses

# Copy test directory
COPY tests /workspace/tests
WORKDIR /workspace
