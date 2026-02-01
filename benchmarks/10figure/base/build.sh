#!/bin/bash
set -e

# Build harbor-10figure:base Docker image with corpus
# Clones all 4 Phase 1 repos at pinned versions via shallow clone

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

# Pinned repo versions
KUBERNETES_TAG="v1.29.3"
DJANGO_TAG="5.0.4"
ENVOY_TAG="v1.29.2"
TENSORFLOW_TAG="v2.16.1"

KUBERNETES_REPO="https://github.com/kubernetes/kubernetes.git"
DJANGO_REPO="https://github.com/django/django.git"
ENVOY_REPO="https://github.com/envoyproxy/envoy.git"
TENSORFLOW_REPO="https://github.com/tensorflow/tensorflow.git"

# Check for pre-built corpus or clone fresh
CORPUS_PATH="${CORPUS_PATH:-}"

if [ -n "$CORPUS_PATH" ] && [ -d "$CORPUS_PATH" ]; then
    echo "Using pre-built corpus at $CORPUS_PATH"
    if [ ! -d "$CORPUS_PATH/src/kubernetes" ] || [ ! -d "$CORPUS_PATH/src/envoy" ] || \
       [ ! -d "$CORPUS_PATH/src/django" ] || [ ! -d "$CORPUS_PATH/src/tensorflow" ]; then
        echo "Error: Corpus at $CORPUS_PATH missing required repos under src/"
        echo "Expected: src/kubernetes, src/envoy, src/django, src/tensorflow"
        exit 1
    fi
    USE_PREBUILT=true
else
    echo "No CORPUS_PATH set or directory missing. Will clone repos at pinned versions."
    USE_PREBUILT=false
fi

TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

if [ "$USE_PREBUILT" = true ]; then
    echo "Copying pre-built corpus to build context..."
    cp -r "$CORPUS_PATH" "$TEMP_DIR/10Figure-Codebases"
else
    echo "Cloning repos at pinned versions (shallow clones)..."
    CORPUS_DIR="$TEMP_DIR/10Figure-Codebases"
    mkdir -p "$CORPUS_DIR/src"

    echo ""
    echo "Cloning Kubernetes @ $KUBERNETES_TAG ..."
    git clone --depth 1 --branch "$KUBERNETES_TAG" "$KUBERNETES_REPO" "$CORPUS_DIR/src/kubernetes"

    echo ""
    echo "Cloning Django @ $DJANGO_TAG ..."
    git clone --depth 1 --branch "$DJANGO_TAG" "$DJANGO_REPO" "$CORPUS_DIR/src/django"

    echo ""
    echo "Cloning Envoy @ $ENVOY_TAG ..."
    git clone --depth 1 --branch "$ENVOY_TAG" "$ENVOY_REPO" "$CORPUS_DIR/src/envoy"

    echo ""
    echo "Cloning TensorFlow @ $TENSORFLOW_TAG ..."
    git clone --depth 1 --branch "$TENSORFLOW_TAG" "$TENSORFLOW_REPO" "$CORPUS_DIR/src/tensorflow"

    # Create minimal scaffolding expected by Dockerfile
    mkdir -p "$CORPUS_DIR/tasks"
    mkdir -p "$CORPUS_DIR/scripts"

    # Create a minimal requirements.txt if not present
    if [ ! -f "$CORPUS_DIR/requirements.txt" ]; then
        echo "# Minimal requirements for 10Figure benchmark" > "$CORPUS_DIR/requirements.txt"
        echo "pyyaml>=6.0" >> "$CORPUS_DIR/requirements.txt"
    fi

    echo ""
    echo "All repos cloned successfully."
fi

echo ""
echo "Building harbor-10figure:base Docker image..."
echo "Repo versions: Kubernetes=$KUBERNETES_TAG, Django=$DJANGO_TAG, Envoy=$ENVOY_TAG, TensorFlow=$TENSORFLOW_TAG"
echo "This will take several minutes (corpus is ~5GB)..."
echo ""

cd "$SCRIPT_DIR"
podman build -t harbor-10figure:base -f Dockerfile "$TEMP_DIR"

echo ""
echo "Image built successfully: harbor-10figure:base"
echo ""
echo "Pinned versions:"
echo "  Kubernetes: $KUBERNETES_TAG"
echo "  Django:     $DJANGO_TAG"
echo "  Envoy:      $ENVOY_TAG"
echo "  TensorFlow: $TENSORFLOW_TAG"
echo ""
echo "To verify:"
echo "  docker run --rm harbor-10figure:base ls -la /10figure/src"
