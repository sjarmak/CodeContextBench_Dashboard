FROM gcc:13

WORKDIR /workspace

# Install dependencies
RUN apt-get update && apt-get install -y cmake ninja-build git

# Clone PyTorch repository
RUN git clone https://github.com/pytorch/pytorch.git /workspace && \
    cd /workspace && \
    git checkout 65d346ff8c711731c6f2db4b3c045422bf87c582 && \
    git submodule update --init --recursive

# Task setup complete
