FROM gcc:13

WORKDIR /workspace

# Install dependencies
RUN apt-get update && apt-get install -y cmake ninja-build git

# Clone PyTorch repository
RUN git clone https://github.com/pytorch/pytorch.git /workspace && \
    cd /workspace && \
    git checkout c2e3cc7aedb2e7d89443225c7cccd08a0f8a3587 && \
    git submodule update --init --recursive

# Task setup complete
