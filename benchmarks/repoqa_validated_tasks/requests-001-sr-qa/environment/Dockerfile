FROM ubuntu:22.04

RUN apt-get update && apt-get install -y \
    python3 python3-pip \
    git curl \
    && rm -rf /var/lib/apt/lists/*

# Clone repository at specific commit
RUN git clone https://github.com/requests/requests.git /app/repo && \
    cd /app/repo && \
    git checkout 70298332899f25826e35e42f8d83425124f755a5

# Install Python dependencies for verification (if needed)
RUN pip install --no-cache-dir -q \
    tree-sitter==0.20.1 \
    python-dotenv

WORKDIR /app
