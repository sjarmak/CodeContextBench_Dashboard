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
RUN git fetch origin 76b8fdafad537579cd97b5ec2502c6ac3bc473e0 2>/dev/null || true
RUN git checkout 76b8fdafad537579cd97b5ec2502c6ac3bc473e0 || git checkout -B fix 76b8fdafad537579cd97b5ec2502c6ac3bc473e0

# Install PyTorch build dependencies
RUN pip install -q numpy pyyaml mkl mkl-service setuptools cffi typing_extensions future six requests dataclasses
