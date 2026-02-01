# Base Docker Image

This directory contains the Dockerfile and build script for `harbor-10figure:base`, the foundational image containing the 10Figure-Codebases corpus with all 4 Phase 1 repositories.

## Pinned Repository Versions

| Repository | Version | Shallow Clone | Approx Size |
|------------|---------|---------------|-------------|
| [Kubernetes](https://github.com/kubernetes/kubernetes) | v1.29.3 | `--depth 1` | ~800MB |
| [Django](https://github.com/django/django) | 5.0.4 | `--depth 1` | ~70MB |
| [Envoy](https://github.com/envoyproxy/envoy) | v1.29.2 | `--depth 1` | ~400MB |
| [TensorFlow](https://github.com/tensorflow/tensorflow) | v2.16.1 | `--depth 1` | ~700MB |

All repos are cloned with `--depth 1` (shallow clone) to minimize image size.

## Image Contents

The base image includes:
- Ubuntu 22.04 base
- Python 3 + dependencies
- Git, build tools, jq
- All 4 repos at `/10figure/src/`:
  - `/10figure/src/kubernetes/` (Kubernetes v1.29.3)
  - `/10figure/src/django/` (Django 5.0.4)
  - `/10figure/src/envoy/` (Envoy v1.29.2)
  - `/10figure/src/tensorflow/` (TensorFlow v2.16.1)
- Validator script at `/10figure/scripts/validate_patch.py`

## Expected Image Size

~6-8GB (includes all 4 repos via shallow clones + system dependencies)

## Building the Image

### Option 1: Auto-clone repos (no pre-built corpus needed)

```bash
./build.sh
```

This will shallow-clone all 4 repos at their pinned versions into a temp directory and build the image.

### Option 2: Use pre-built corpus

```bash
CORPUS_PATH=~/10Figure-Codebases ./build.sh
```

If you already have a built corpus at `~/10Figure-Codebases` with `src/kubernetes`, `src/django`, `src/envoy`, `src/tensorflow`, the script will use it directly instead of cloning.

## Verification

```bash
# Check all 4 repos are present
docker run --rm harbor-10figure:base ls -la /10figure/src

# Should show: kubernetes, django, envoy, tensorflow
```

## Usage in Harbor Tasks

Harbor tasks inherit from this base image:

```dockerfile
FROM harbor-10figure:base

ENV REPO_ROOT=/10figure/src/kubernetes
RUN echo "$REPO_ROOT" > /task/repo_path
```

This avoids rebuilding the corpus for every task, leveraging Docker layer caching.

## Alternative: Podman

If using Podman instead of Docker:

```bash
# The build.sh script uses podman by default
# Replace 'podman' with 'docker' in build.sh if needed
```
