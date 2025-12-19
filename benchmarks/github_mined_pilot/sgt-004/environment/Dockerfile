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
RUN git fetch origin 3ecf7c3d79894f8aa7e05aaacd288781c6e5da51 2>/dev/null || true
RUN git checkout 3ecf7c3d79894f8aa7e05aaacd288781c6e5da51 || git checkout -B fix 3ecf7c3d79894f8aa7e05aaacd288781c6e5da51

# Install PyTorch build dependencies
RUN pip install -q numpy pyyaml mkl mkl-service setuptools cffi typing_extensions future six requests dataclasses
