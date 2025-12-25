#!/usr/bin/env bash
# Remove lingering Harbor containers in Podman so each evaluation starts clean.

set -euo pipefail

if ! command -v podman >/dev/null 2>&1; then
  echo "Podman is not installed. Skipping cleanup." >&2
  exit 0
fi

if ! podman ps >/dev/null 2>&1; then
  echo "Podman is installed but not reachable. Is the Podman machine running?" >&2
  exit 1
fi

mapfile -t stale_ids < <(podman ps --all --format '{{.ID}} {{.Image}}' | awk '$2 ~ /hb__/ {print $1}')

if ((${#stale_ids[@]} == 0)); then
  echo "No Harbor containers to clean up."
  exit 0
fi

echo "Stopping stale Harbor containers: ${stale_ids[*]}"
podman stop "${stale_ids[@]}" >/dev/null

echo "Removing stale Harbor containers..."
podman rm "${stale_ids[@]}" >/dev/null

echo "✓ Harbor containers cleaned up"
