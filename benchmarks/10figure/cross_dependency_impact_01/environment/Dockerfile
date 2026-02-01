FROM harbor-10figure:base

# Cross-repo task: Django + TensorFlow
ENV TASK_ID=cross_dependency_impact_01
ENV TASK_TYPE=cross_file_reasoning
ENV REPOS="django tensorflow"

# Create task directory structure
RUN mkdir -p /task/tests /logs/agent /logs/verifier

# Copy task files
COPY instruction.md /task/instruction.md
COPY task.toml /task/task.toml
COPY task.yaml /task/task.yaml
COPY tests/ /task/tests/

WORKDIR /workspace
