FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --no-cache-dir \
    duckdb \
    pandas \
    numpy \
    pyyaml \
    matplotlib \
    seaborn

WORKDIR /app

COPY data /data
COPY task /app/task

CMD ["/bin/bash"]
