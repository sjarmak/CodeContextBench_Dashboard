FROM pytorch/pytorch:latest

WORKDIR /src

# Install additional build dependencies
RUN apt-get update && apt-get install -y \
    git \
    cmake \
    ninja-build \
    && rm -rf /var/lib/apt/lists/*

# Clone PyTorch repository at pre_fix_rev
RUN git clone https://github.com/pytorch/pytorch . 2>/dev/null || true
RUN git fetch origin 5811a8d7da873dd699ff6687092c225caffcf1bb 2>/dev/null || true
RUN git checkout 5811a8d7da873dd699ff6687092c225caffcf1bb || git checkout -B fix 5811a8d7da873dd699ff6687092c225caffcf1bb

# Install PyTorch build dependencies
RUN pip install -q numpy pyyaml mkl mkl-service setuptools cffi typing_extensions future six requests dataclasses
