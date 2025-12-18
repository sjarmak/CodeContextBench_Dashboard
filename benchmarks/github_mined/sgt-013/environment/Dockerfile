FROM gcc:13

WORKDIR /workspace

# Install dependencies
RUN apt-get update && apt-get install -y cmake ninja-build git

# Clone PyTorch repository
RUN git clone https://github.com/pytorch/pytorch.git /workspace && \
    cd /workspace && \
    git checkout ee7434be822cf6e75b4566d8159f550ee233d8ae && \
    git submodule update --init --recursive

# Task setup complete
