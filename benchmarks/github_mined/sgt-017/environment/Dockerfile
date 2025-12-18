FROM gcc:13

WORKDIR /workspace

# Install dependencies
RUN apt-get update && apt-get install -y cmake ninja-build git

# Clone PyTorch repository
RUN git clone https://github.com/pytorch/pytorch.git /workspace && \
    cd /workspace && \
    git checkout bebabd7fce29ea49b9269aeaa9fe3f34a3e1127e && \
    git submodule update --init --recursive

# Task setup complete
