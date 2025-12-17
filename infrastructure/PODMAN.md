# Podman Setup for CodeContextBench

CodeContextBench supports **Podman** as the primary container runtime for Harbor benchmark execution.

## Quick Start

### Prerequisites

- Podman 5.0+ installed (`podman --version`)
- `podman-compose` installed (`pip install podman-compose`)
- Harbor installed (`uv tool install harbor`)
- `docker` wrapper script at `~/bin/docker` (see [Setup](#setup) below)

### Environment Setup

Set up your environment before running benchmarks:

```bash
# 1. Ensure wrapper is in PATH
export PATH="$HOME/bin:$PATH"

# 2. Load credentials from .env.local
source infrastructure/load-env.sh

# 3. Run Harbor with Podman
harbor run -d terminal-bench@2.0 \
  --agent-import-path agents:ClaudeAgent \
  --task-name "cross_file_reasoning_01" \
  -n 1
```

## Why Podman?

- **No Docker Desktop licensing** - Rootless, free, open-source
- **Better security** - Rootless by default, no daemon running as root
- **Drop-in replacement** - Works with Harbor via our docker wrapper script
- **CI/CD friendly** - Better container isolation, works in restricted environments

## How It Works

Harbor hardcodes `docker` and `docker compose` commands. We intercept these with a wrapper script at `~/bin/docker` that:

1. **Translates `docker compose` commands** to `podman-compose` or `podman` as needed
2. **Handles incompatibilities** (e.g., `podman-compose` doesn't support `cp` or `-it` flags)
3. **Maps container names** from Docker compose service names to Podman container IDs

### Command Translation

| Harbor Command | Translation |
|---|---|
| `docker compose up` | `podman-compose up` |
| `docker compose exec -it` | `podman exec` (with flags adjusted) |
| `docker compose cp` | `podman cp` (finds container by project name) |
| `docker run` | `podman run` |
| `docker ps` | `podman ps` |

## Setup

### Option 1: Using Existing Wrapper (Recommended)

The wrapper script is already at `~/bin/docker`. Simply ensure it's in your PATH:

```bash
# Verify wrapper exists and is executable
ls -la ~/bin/docker
chmod +x ~/bin/docker

# Add to PATH (add to .bashrc or .zshrc to persist)
export PATH="$HOME/bin:$PATH"

# Verify it works
docker --version  # Should show Podman version
docker compose --version  # Should show podman-compose version
```

### Option 2: Install Wrapper Manually

If the wrapper doesn't exist:

```bash
# Create ~/.bin directory if needed
mkdir -p ~/.bin

# Copy wrapper from this repository
cp infrastructure/docker-wrapper.sh ~/.bin/docker

# Make executable
chmod +x ~/.bin/docker

# Add to PATH
export PATH="$HOME/.bin:$PATH"

# Verify
docker --version
```

### Podman Machine (macOS)

On macOS, start Podman machine before running benchmarks:

```bash
# Initialize (one-time)
podman machine init --cpus 4 --memory 4096

# Start for each session
podman machine start

# Verify
podman info
```

To start Podman machine automatically on login, see Podman's documentation.

## Troubleshooting

### "docker: command not found"

**Solution**: Ensure wrapper is in PATH

```bash
which docker  # Should point to ~/bin/docker
export PATH="$HOME/bin:$PATH"
```

### "Error: Could not find container for project"

**Cause**: Wrapper can't find the container Harbor created.

**Solution**: Check what containers exist:

```bash
podman ps
podman ps --all
```

Ensure Harbor has started containers successfully.

### "podman-compose: command not found"

**Solution**: Install podman-compose

```bash
pip install podman-compose

# Verify
podman-compose --version
```

### Podman machine won't start (macOS)

```bash
# Reset machine
podman machine rm default
podman machine init --cpus 4 --memory 4096
podman machine start
```

### Permission denied executing podman

**Solution**: Ensure Podman is running in rootless mode

```bash
# Verify rootless
podman info | grep -i rootless

# Migrate to rootless if needed
podman system migrate
```

## Performance Tips

1. **Allocate resources to Podman machine** (macOS):
   ```bash
   podman machine set --cpus 4 --memory 4096
   podman machine start
   ```

2. **Use tmpfs for fast I/O**:
   ```bash
   podman run --tmpfs /tmp ...
   ```

3. **Cache images locally**:
   ```bash
   podman pull <image>  # Cache before run
   ```

4. **Monitor resource usage**:
   ```bash
   podman stats
   ```

## Switching Between Podman and Docker

### Use Podman (default)

```bash
export PATH="$HOME/bin:$PATH"
export CONTAINER_RUNTIME=podman
# Harbor will use podman via wrapper
```

### Use Docker Desktop (if installed)

```bash
# Remove wrapper from PATH or use direct path
unset CONTAINER_RUNTIME
/usr/local/bin/docker --version  # Use Docker directly
```

## Integration with Harbor

Harbor expects a `docker` command in PATH. The wrapper at `~/bin/docker` satisfies this by:

1. Accepting the same CLI flags as Docker
2. Translating incompatible commands
3. Delegating to `podman` or `podman-compose`

This allows Harbor to work seamlessly with Podman without code changes.

## See Also

- [Infrastructure README](./README.md) - Container and dataset configuration
- [docs/DEVELOPMENT.md](../docs/DEVELOPMENT.md) - Development setup and workflows
- [Podman Documentation](https://docs.podman.io/) - Official Podman docs
