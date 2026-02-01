FROM harbor-10figure:base

# Cross-repo task: Kubernetes + Envoy
ENV TASK_ID=cross_api_tracing_01
ENV TASK_TYPE=cross_file_reasoning
ENV REPOS="kubernetes envoy"

# Create task directory structure
RUN mkdir -p /task/tests /logs/agent /logs/verifier

# Copy task files
COPY instruction.md /task/instruction.md
COPY task.toml /task/task.toml
COPY task.yaml /task/task.yaml
COPY tests/ /task/tests/

WORKDIR /workspace
