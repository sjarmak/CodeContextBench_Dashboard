FROM harbor-10figure:base

ENV TASK_ID=cross_bug_localization_01
ENV TASK_TYPE=bug_localization
ENV REPOS="kubernetes django"

RUN mkdir -p /task/tests /logs/agent /logs/verifier

COPY instruction.md /task/instruction.md
COPY task.toml /task/task.toml
COPY task.yaml /task/task.yaml
COPY tests/ /task/tests/

WORKDIR /workspace
