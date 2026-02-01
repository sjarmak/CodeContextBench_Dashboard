FROM python:3.11-slim

# Install network diagnostic tools
RUN apt-get update && apt-get install -y \
    curl \
    dnsutils \
    iputils-ping \
    net-tools \
    iproute2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /testbed

# Create initial marker file
RUN echo "Network diagnostic environment ready" > /testbed/readme.txt
