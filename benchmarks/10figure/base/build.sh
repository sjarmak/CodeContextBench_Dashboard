#!/bin/bash
set -e

# Build harbor-10figure:base Docker image with multi-repo corpus
# Uses multi-stage build: builder strips .git, runtime has only source + tools

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Pinned commit SHAs for reproducibility
KUBERNETES_SHA="ef274e869c3ea3d4042fada38a56221283a42362"
ENVOY_SHA="782c6caee166a8414097f548f7309114863379a8"
DJANGO_SHA="c4e07f94ebc1f9eaa3dae7b3dc6a2b9832182a10"
TENSORFLOW_SHA="420baf67d8c9fce3b66e435e7a4fdec57ecf4122"

# Check if 10Figure-Codebases exists
CORPUS_PATH="${CORPUS_PATH:-$HOME/10Figure-Codebases}"

if [ ! -d "$CORPUS_PATH" ]; then
    echo "Error: 10Figure-Codebases not found at $CORPUS_PATH"
    echo "Set CORPUS_PATH environment variable or clone to ~/10Figure-Codebases"
    exit 1
fi

# Validate all 4 repos exist
for repo in kubernetes envoy django tensorflow; do
    if [ ! -d "$CORPUS_PATH/src/$repo" ]; then
        echo "Error: $repo not found in $CORPUS_PATH/src/"
        echo "Run 'make build-corpus' in $CORPUS_PATH first"
        exit 1
    fi
done

echo "Building harbor-10figure:base Docker image (multi-stage build)..."
echo "Corpus path: $CORPUS_PATH"
echo ""
echo "Repos included:"
echo "  kubernetes @ ${KUBERNETES_SHA:0:8}"
echo "  envoy      @ ${ENVOY_SHA:0:8}"
echo "  django     @ ${DJANGO_SHA:0:8}"
echo "  tensorflow @ ${TENSORFLOW_SHA:0:8}"
echo ""

# Copy corpus to build context
TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

echo "Copying corpus to build context..."
cp -r "$CORPUS_PATH" "$TEMP_DIR/10Figure-Codebases"

# Build image using multi-stage Dockerfile
cd "$SCRIPT_DIR"
podman build -t harbor-10figure:base -f Dockerfile "$TEMP_DIR"

# Report image size
IMAGE_SIZE=$(podman image inspect harbor-10figure:base --format '{{.Size}}' 2>/dev/null || echo "unknown")
if [ "$IMAGE_SIZE" != "unknown" ]; then
    IMAGE_SIZE_GB=$(echo "scale=2; $IMAGE_SIZE / 1073741824" | bc 2>/dev/null || echo "N/A")
    echo ""
    echo "Image size: ${IMAGE_SIZE_GB}GB"
fi

echo ""
echo "Build complete: harbor-10figure:base"
echo ""
echo "To verify:"
echo "  docker run --rm harbor-10figure:base ls -la /10figure/src"
echo "  docker run --rm harbor-10figure:base echo \$KUBERNETES_SHA"
