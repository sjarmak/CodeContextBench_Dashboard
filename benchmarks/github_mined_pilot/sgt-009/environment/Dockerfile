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
RUN git fetch origin 863edc787f5fa7950e0f3f86d4952641e1ef9c2c 2>/dev/null || true
RUN git checkout 863edc787f5fa7950e0f3f86d4952641e1ef9c2c || git checkout -B fix 863edc787f5fa7950e0f3f86d4952641e1ef9c2c

# Install PyTorch build dependencies
RUN pip install -q numpy pyyaml mkl mkl-service setuptools cffi typing_extensions future six requests dataclasses
