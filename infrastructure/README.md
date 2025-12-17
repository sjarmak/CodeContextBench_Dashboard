# Infrastructure

Container, dataset, and deployment configuration for CodeContextBench.

## Directory Structure

- **PODMAN.md** - Podman setup and configuration (primary container runtime)
- **docker-wrapper.sh** - Docker compatibility layer
- **harbor-config.yaml** - Harbor orchestration settings
- **datasets.yaml** - External dataset references (10Figure, etc.)

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

- **CONTAINER_RUNTIME**: "podman" (default) or "docker"
- **HARBOR_10FIGURE**: Path to 10Figure dataset (default: /10figure)
- **SRC_ACCESS_TOKEN**: Sourcegraph API token (for Sourcegraph MCP tests)
- **SOURCEGRAPH_URL**: Sourcegraph instance URL (default: https://sourcegraph.sourcegraph.com)

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
