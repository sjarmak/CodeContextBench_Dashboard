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
RUN git fetch origin e3e93c7107830c13f4139c3a62fda62c6b84bbf5 2>/dev/null || true
RUN git checkout e3e93c7107830c13f4139c3a62fda62c6b84bbf5 || git checkout -B fix e3e93c7107830c13f4139c3a62fda62c6b84bbf5

# Install PyTorch build dependencies
RUN pip install -q numpy pyyaml mkl mkl-service setuptools cffi typing_extensions future six requests dataclasses
