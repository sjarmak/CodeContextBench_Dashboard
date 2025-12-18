# Infrastructure

Container, dataset, and deployment configuration for CodeContextBench.

## Standard Setup: Harbor + Daytona on Podman (macOS)

**Current standard**: We run Harbor using Podman with **Daytona** as the execution backend. This setup is permanent.

Key components:
- **Podman machine** - Rootless container runtime (replaces Docker Desktop)
- **Docker shim** - Compatibility layer at `~/.bin/docker` that translates Docker → Podman
- **Daytona** - Sandbox execution backend (API-driven, no local Docker needed)
- **Harbor venv** - Isolated environment that sets up DOCKER_HOST, PATH, and Daytona credentials

See **PODMAN.md** for complete setup and troubleshooting.

## Directory Structure

- **PODMAN.md** - Harbor + Daytona + Podman setup guide (**START HERE**)
- **docker-wrapper.sh** - Docker→Podman compatibility shim (executable)
- **harbor-config.yaml** - Harbor orchestration settings (container runtime, agents, timeouts)
- **datasets.yaml** - External dataset references (10Figure corpus contract)
- **load-env.sh** - Load environment variables from .env.local before running benchmarks
- **README.md** - This file

See **docs/10FIGURE.md** for detailed 10Figure corpus setup and usage instructions.

## Quick Reference: Running Harbor

```bash
# Activate Harbor venv (auto-loads Daytona credentials and sets DOCKER_HOST)
source harbor/bin/activate

# Run Harbor with Daytona backend
harbor run \
  --dataset swebench-verified@1.0 \
  --agent oracle \
  --env daytona \
  -n 1
```

That's it. The venv handles all setup.

## Key Concepts

### Harbor + Daytona Workflow

Harbor provides task orchestration; Daytona provides sandbox execution:
1. Harbor reads task manifests and prepares environment
2. Harbor creates Daytona sandbox (via API)
3. Agent runs in sandbox with task files mounted
4. Harbor collects logs and results

### External Datasets

The 10Figure-Codebases corpus (~5GB) is not version-controlled. Instead:
- Reference via symlink: `ln -s /Users/sjarmak/10Figure-Codebases ./10figure`
- Or set environment variable: `export HARBOR_10FIGURE=/path/to/corpus`
- Tasks reference repos at `/10figure/src/<repo_name>`

## Environment Variables

All required credentials should be set in `.env.local` (created from `.env.local.example`):

### Setup

```bash
# 1. Copy example to local config
cp .env.local.example .env.local

# 2. Edit with your actual credentials
# ANTHROPIC_API_KEY: Get from https://console.anthropic.com/
# SRC_ACCESS_TOKEN: Get from https://sourcegraph.sourcegraph.com/user/settings/tokens
nano .env.local

# 3. Load before running benchmarks
source infrastructure/load-env.sh
```

### Variables

- **ANTHROPIC_API_KEY** (required): Claude API key
- **SRC_ACCESS_TOKEN** (optional): Sourcegraph API token (required for Claude+MCP agent)
- **SOURCEGRAPH_URL** (optional): Sourcegraph instance URL (default: https://sourcegraph.sourcegraph.com)
- **HARBOR_10FIGURE** (optional): Path to 10Figure dataset (default: /10figure in containers)
- **CONTAINER_RUNTIME** (optional): "podman" (default) or "docker"

**Never commit .env.local to version control.** The file is in `.gitignore`.

## Troubleshooting

### Container won't start
```bash
podman ps --all  # Check all containers
podman logs <container>  # View logs
podman run -it harbor-10figure:base /bin/bash  # Debug interactively
```

### Permission denied errors
```bash
# Podman may need to be configured for rootless mode
podman system migrate
```

### Task files not mounted
Check that task.toml is in the correct Harbor manifest directory.
