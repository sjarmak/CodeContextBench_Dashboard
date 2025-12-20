#!/bin/bash
# Docker disk space cleanup script
# Safely removes stopped containers, dangling images, and unused networks

set -e

echo "🧹 Docker cleanup started..."

# Count items before
BEFORE=$(docker system df | grep "Images\|Containers" | awk '{s+=$3} END {print s}')

# Remove stopped containers (safe - won't affect running tasks)
echo "Removing stopped containers..."
docker container prune -f --filter "until=24h" 2>/dev/null || true

# Remove dangling images (safe - unreferenced image layers)
echo "Removing dangling images..."
docker image prune -f 2>/dev/null || true

# Remove unused networks
echo "Removing unused networks..."
docker network prune -f 2>/dev/null || true

# Show final state
echo ""
echo "✅ Cleanup complete"
docker system df

echo ""
echo "💡 To free more space (careful - stops all running harbor tasks):"
echo "   docker stop \$(docker ps -q) && docker system prune -a -f"
