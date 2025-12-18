#!/usr/bin/env python3
"""
Test container network connectivity to Sourcegraph.

This script helps diagnose why MCP connection fails in containers.
It creates a simple test container that attempts to connect to Sourcegraph.

Usage:
    python runners/test_container_network.py
"""
import asyncio
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

def run_cmd(cmd, cwd=None):
    """Run a command and return output."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.stdout + result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return "TIMEOUT", -1
    except Exception as e:
        return str(e), -1

def test_network_connectivity():
    """Test network connectivity from local machine first."""
    print("=" * 80)
    print("PHASE 1: Local Network Test (from your machine)")
    print("=" * 80)
    
    sg_url = "https://sourcegraph.sourcegraph.com"
    
    tests = [
        (f"curl -s -o /dev/null -w '%{{http_code}}' {sg_url}/health", "HTTP status code"),
        (f"curl -I {sg_url}/health", "HTTP headers"),
        (f"nslookup sourcegraph.com", "DNS resolution"),
    ]
    
    results = {}
    for cmd, desc in tests:
        print(f"\n  Testing: {desc}")
        print(f"  Command: {cmd}")
        output, code = run_cmd(cmd)
        print(f"  Result: {output[:200]}...")
        results[desc] = code == 0
    
    return results

def create_dockerfile_with_network_test():
    """Create a Dockerfile that tests network connectivity."""
    return """FROM python:3.12-slim

WORKDIR /workspace

# Install curl and wget
RUN apt-get update && apt-get install -y curl wget dnsutils && rm -rf /var/lib/apt/lists/*

# Create test script using printf to avoid heredoc issues with Docker
RUN printf '#!/bin/bash\\nset +e\\necho "=== Container Network Test ==="\\necho "Testing from inside container..."\\necho ""\\necho "1. Testing DNS resolution:"\\nnslookup sourcegraph.com\\necho ""\\necho "2. Testing curl to Sourcegraph:"\\ncurl -v --max-time 10 https://sourcegraph.sourcegraph.com/health\\necho ""\\necho "Exit code: $?"\\necho ""\\necho "3. Testing wget:"\\nwget --spider -v https://sourcegraph.sourcegraph.com/health 2>&1\\necho ""\\necho "Exit code: $?"\\necho ""\\necho "4. Checking environment:"\\necho "HTTPS_PROXY: ${HTTPS_PROXY:-not set}"\\necho "HTTP_PROXY: ${HTTP_PROXY:-not set}"\\necho "NO_PROXY: ${NO_PROXY:-not set}"\\necho ""\\necho "=== Test Complete ==="\\n' > /test_network.sh && chmod +x /test_network.sh

CMD ["/bin/bash", "/test_network.sh"]
"""

def test_with_docker():
    """Build and run a test container."""
    print("\n" + "=" * 80)
    print("PHASE 2: Docker Container Network Test")
    print("=" * 80)
    
    # Check if Docker is available
    docker_check, code = run_cmd("docker --version")
    if code != 0:
        print("⚠️  Docker is not available. Skipping container test.")
        return False
    
    print(f"✓ Docker is available: {docker_check.strip()}")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Create Dockerfile
        dockerfile_path = tmpdir / "Dockerfile"
        dockerfile_path.write_text(create_dockerfile_with_network_test())
        
        # Build image
        image_name = "test-network-connectivity:latest"
        print(f"\n  Building Docker image: {image_name}")
        build_output, build_code = run_cmd(f"docker build -t {image_name} {tmpdir}")
        
        if build_code != 0:
            print(f"  ❌ Docker build failed:")
            print(build_output)
            return False
        
        print(f"  ✓ Docker image built")
        
        # Run container
        print(f"\n  Running container network test...")
        run_output, run_code = run_cmd(f"docker run --rm {image_name}")
        
        print("\n  Container output:")
        print("-" * 80)
        print(run_output)
        print("-" * 80)
        
        # Cleanup
        run_cmd(f"docker rmi {image_name}")
        
        # Check results
        success = "200 OK" in run_output or "200" in run_output or "Exit code: 0" in run_output
        return success

def test_with_harbor_daytona():
    """Test connectivity using Harbor's actual environment setup."""
    print("\n" + "=" * 80)
    print("PHASE 3: Harbor/Daytona Environment Test")
    print("=" * 80)
    
    # Try to import Harbor
    try:
        from harbor.environments.daytona import DaytonaEnvironment
        print("✓ Harbor is available")
    except ImportError:
        print("⚠️  Harbor is not available locally. Skipping this test.")
        return False
    
    # Check if Daytona is configured
    daytona_url = os.environ.get("DAYTONA_URL")
    if not daytona_url:
        print("⚠️  DAYTONA_URL not set. Cannot test with real Daytona environment.")
        print("    Set DAYTONA_URL to test with actual Harbor infrastructure.")
        return False
    
    print(f"  Testing with Daytona: {daytona_url}")
    
    async def run_test():
        try:
            env = DaytonaEnvironment()
            
            # Create a test task
            test_script = """#!/bin/bash
echo "=== Harbor Container Network Test ==="
echo "Testing from Harbor container..."
echo ""

echo "1. Test curl to Sourcegraph:"
curl -v --max-time 10 https://sourcegraph.sourcegraph.com/health
echo ""

echo "2. Check proxy settings:"
echo "HTTPS_PROXY: ${HTTPS_PROXY:-not set}"
echo "HTTP_PROXY: ${HTTP_PROXY:-not set}"

echo "=== Test Complete ==="
"""
            
            # This would require actual Harbor setup - skip for now
            print("  ⚠️  Skipping real Harbor test (requires infrastructure setup)")
            return False
        except Exception as e:
            print(f"  ❌ Harbor test error: {e}")
            return False
    
    return asyncio.run(run_test())

def main():
    """Run all network tests."""
    print("\n" + "🔍 " * 20)
    print("Container Network Connectivity Diagnostic")
    print("🔍 " * 20 + "\n")
    
    # Phase 1: Local tests
    print("This script will:")
    print("  1. Test network connectivity from your local machine")
    print("  2. Test network connectivity inside a Docker container")
    print("  3. Test with Harbor/Daytona environment (if configured)")
    print("")
    print("This helps identify if the MCP network issue is due to:")
    print("  • Your network/firewall (Phase 1 fails)")
    print("  • Docker container network isolation (Phase 2 fails)")
    print("  • Harbor/Daytona infrastructure (Phase 3 fails)")
    
    local_results = test_network_connectivity()
    
    # Phase 2: Docker test
    docker_results = test_with_docker()
    
    # Phase 3: Harbor test
    harbor_results = test_with_harbor_daytona()
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    print(f"\nLocal connectivity: {'✅ PASSED' if all(local_results.values()) else '❌ FAILED'}")
    if not all(local_results.values()):
        print("  → Your machine cannot reach sourcegraph.com. Check your network/firewall.")
    
    print(f"\nDocker connectivity: {'✅ PASSED' if docker_results else '⚠️  NOT TESTED'}")
    if docker_results is False:
        print("  → Containers on your machine cannot reach sourcegraph.com.")
        print("  → Check Docker's network settings or proxy configuration.")
    
    print(f"\nHarbor/Daytona: {'✅ TESTED' if harbor_results else '⚠️  NOT TESTED'}")
    
    print("\n" + "=" * 80)
    print("Next Steps:")
    print("=" * 80)
    if all(local_results.values()) and docker_results is False:
        print("""
1. Check Docker's network settings:
   - Run: docker network ls
   - Check if containers can reach external networks
   
2. Check for proxies:
   - Run: docker run alpine env | grep PROXY
   - If proxies are set, MCP HTTP client may need proxy configuration
   
3. Configure Docker to use a specific DNS:
   - Edit ~/.docker/daemon.json
   - Add: "dns": ["8.8.8.8", "8.8.4.4"]
   - Restart Docker daemon
        """)
    elif all(local_results.values()) and docker_results:
        print("""
✅ Network connectivity works locally and in Docker.
The issue is likely with the MCP configuration or Claude Code's HTTP MCP client.

Next steps:
1. Run a Harbor job with the updated agent that includes network diagnostics
2. Check the agent logs for the network_test.sh output
3. Look for HTTP errors in Claude's initialization logs
        """)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
