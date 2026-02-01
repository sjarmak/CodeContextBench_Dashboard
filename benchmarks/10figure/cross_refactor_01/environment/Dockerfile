FROM harbor-10figure:base

ENV TASK_ID=cross_refactor_01
ENV TASK_TYPE=refactor_rename
ENV REPOS="envoy kubernetes"

RUN mkdir -p /task/tests /logs/agent /logs/verifier

COPY instruction.md /task/instruction.md
COPY task.toml /task/task.toml
COPY task.yaml /task/task.yaml
COPY tests/ /task/tests/

WORKDIR /workspace
