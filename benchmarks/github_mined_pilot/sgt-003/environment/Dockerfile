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
RUN git fetch origin aaa111bbb222aaa111bbb222aaa111bbb222 2>/dev/null || true
RUN git checkout aaa111bbb222aaa111bbb222aaa111bbb222 || git checkout -B fix aaa111bbb222aaa111bbb222aaa111bbb222

# Install PyTorch build dependencies
RUN pip install -q numpy pyyaml mkl mkl-service setuptools cffi typing_extensions future six requests dataclasses

# Copy test directory
COPY tests /workspace/tests
WORKDIR /workspace
