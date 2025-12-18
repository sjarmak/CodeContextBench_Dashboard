# Harbor + Daytona on macOS (Podman-based)

**Current Standard Setup**: We run Harbor using Podman (not Docker Desktop) with **Daytona** as the execution backend. This setup is permanent and should be assumed for all runs.

## Quick Start

### Prerequisites

- Podman 5.0+ with machine (`podman --version`, `podman machine start`)
- `podman-compose` installed (`pip install podman-compose`)
- Harbor installed in dedicated venv (`source harbor/bin/activate`)
- Docker compatibility shim at `~/.bin/docker`
- Daytona API key in `~/.config/daytona/env.sh`

### Running Harbor (Standard)

```bash
# 1. Activate Harbor venv (sets up DOCKER_HOST, PATH, Daytona API key)
source harbor/bin/activate

# 2. Run Harbor with Daytona backend
harbor run \
  --dataset swebench-verified@1.0 \
  --agent oracle \
  --env daytona \
  -n 1
```

That's it. The venv handles:
- Setting `DOCKER_HOST` to Podman socket
- Adding `~/.bin/docker` (Podman shim) to PATH
- Loading Daytona credentials from `~/.config/daytona/env.sh`

## Why Podman?

- **No Docker Desktop licensing** - Rootless, free, open-source
- **Better security** - Rootless by default, no daemon running as root
- **Drop-in replacement** - Works with Harbor via our docker wrapper script
- **CI/CD friendly** - Better container isolation, works in restricted environments

## Container Runtime

**Podman machine** is the actual container runtime. We expose a Docker-compatible API socket from Podman and point all tools at it.

### Key Invariants

```bash
which docker
# → ~/.bin/docker   (Podman shim)

echo $DOCKER_HOST
# → unix://$HOME/.local/share/containers/podman/machine/podman.sock

# Verify socket is live:
curl --unix-socket "$HOME/.local/share/containers/podman/machine/podman.sock" http://d/_ping
# → OK
```

### How It Works

- **Podman machine** - Actual container runtime (rootless VM on macOS)
- **Docker socket** - Exposed at `$HOME/.local/share/containers/podman/machine/podman.sock`
- **Docker shim** (`~/.bin/docker`) - Wrapper that translates Docker commands to Podman

The shim handles incompatibilities that Docker API clients may have:

| Harbor/Tool Command | Translation |
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

On macOS, ensure Podman machine is running:

```bash
# Initialize (one-time, ~10 mins)
podman machine init --cpus 4 --memory 4096

# Start for each session
podman machine start

# Verify it's running
podman info

# Stop when done
podman machine stop
```

To start Podman machine automatically on login, see Podman's documentation.

## Daytona Authentication

**Daytona will silently fail to create sandboxes** if the API key is missing. This shows up in Harbor as "Sandbox not found. Please build the environment first."

### Setup (One-Time)

The Daytona API key is stored permanently at:

```bash
# Canonical location (not in git):
~/.config/daytona/env.sh

# Contents:
export DAYTONA_API_KEY="..."
# optionally:
# export DAYTONA_API_URL="https://app.daytona.io/api"
# export DAYTONA_TARGET="..."
```

This file is sourced automatically during venv activation.

### Verification

After activating the Harbor venv, verify credentials are loaded:

```bash
source harbor/bin/activate

# Check that Daytona API key is set
env | grep DAYTONA_API_KEY

# Check that docker is pointing to Podman
which docker  # → ~/.bin/docker

# Verify Podman socket is accessible
curl --unix-socket "$HOME/.local/share/containers/podman/machine/podman.sock" http://d/_ping
# → OK
```

## Troubleshooting

### "Sandbox not found. Please build the environment first."

**Cause**: Daytona API key is missing or invalid.

**Solution**: Verify Daytona credentials:

```bash
source harbor/bin/activate
env | grep DAYTONA_API_KEY  # Should show the key

# If not set, create or edit ~/.config/daytona/env.sh
cat ~/.config/daytona/env.sh
```

### Harbor fails with "Harbor + Daytona on macOS (Podman-based)" in error

**Cause**: Podman machine is not running or socket is inaccessible.

**Solution**: Start Podman machine and verify socket:

```bash
podman machine start
podman info  # Should work

# Verify socket
curl --unix-socket "$HOME/.local/share/containers/podman/machine/podman.sock" http://d/_ping
# Should return: OK
```

### "docker: command not found"

**Solution**: Ensure wrapper is in PATH and Harbor venv is activated

```bash
source harbor/bin/activate
which docker  # Should point to ~/.bin/docker
```

If not in PATH after activation, verify `.bin/docker` exists:

```bash
ls -la ~/.bin/docker
chmod +x ~/.bin/docker
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

## Sanity Checks

If something breaks, run these checks to diagnose:

```bash
# Check environment setup
env | egrep '^(DAYTONA_|DOCKER_HOST=)'

# Check docker wrapper is in use
which docker  # Should be ~/.bin/docker

# Check Podman is accessible
docker ps

# Check Daytona integration
daytona target list
```

All of these should succeed if setup is correct.

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

## See Also

- [Infrastructure README](./README.md) - Container and dataset configuration
- [docs/DEVELOPMENT.md](../docs/DEVELOPMENT.md) - Development setup and workflows
- [Podman Documentation](https://docs.podman.io/) - Official Podman docs
