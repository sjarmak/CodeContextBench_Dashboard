# Infrastructure

Container, dataset, and deployment configuration for CodeContextBench.

## Directory Structure

- **PODMAN.md** - Podman setup and configuration (primary container runtime)
- **docker-wrapper.sh** - Docker compatibility layer
- **harbor-config.yaml** - Harbor orchestration settings
- **datasets.yaml** - External dataset references (10Figure corpus contract definition)

See **docs/10FIGURE.md** for detailed 10Figure corpus setup and usage instructions.

## Key Concepts

### Podman-First Approach

CodeContextBench uses Podman as the primary container runtime because:
- More secure (rootless by default)
- Better CI/CD integration
- Drop-in Docker compatibility for most use cases

For Docker-only environments, use docker-wrapper.sh:
```bash
export CONTAINER_RUNTIME=docker
./infrastructure/docker-wrapper.sh pull <image>
```

### Harbor Integration

Harbor provides:
- Container orchestration for parallel task execution
- Log collection and artifact gathering
- Standard environment setup (mounting /task/, /10figure/, etc.)
- Timeout and resource management

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
