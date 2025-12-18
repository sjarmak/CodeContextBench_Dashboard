#!/usr/bin/env python3
"""Verify that Sourcegraph MCP is properly configured in a running container.

This script checks if the MCP config file exists and is valid, then optionally
runs Claude to confirm it can see the MCP servers.
"""

import json
import os
import subprocess
import sys
from pathlib import Path


def check_mcp_config_file(container_id: str = None) -> bool:
    """Check if /root/.claude/mcp.json exists and is valid."""
    if container_id:
        # Docker exec check
        result = subprocess.run(
            ["docker", "exec", container_id, "test", "-f", "/root/.claude/mcp.json"],
            capture_output=True
        )
        if result.returncode != 0:
            print("❌ /root/.claude/mcp.json does not exist in container")
            return False
        
        # Read and validate
        result = subprocess.run(
            ["docker", "exec", container_id, "cat", "/root/.claude/mcp.json"],
            capture_output=True,
            text=True
        )
        try:
            config = json.loads(result.stdout)
            print("✅ /root/.claude/mcp.json exists and is valid JSON")
            print(f"   MCP Servers configured: {list(config.get('mcpServers', {}).keys())}")
            return True
        except json.JSONDecodeError as e:
            print(f"❌ /root/.claude/mcp.json is not valid JSON: {e}")
            return False
    else:
        # Local file check
        mcp_path = Path.home() / ".claude" / "mcp.json"
        if not mcp_path.exists():
            print(f"❌ {mcp_path} does not exist")
            return False
        
        try:
            with open(mcp_path) as f:
                config = json.load(f)
            print(f"✅ {mcp_path} exists and is valid JSON")
            print(f"   MCP Servers configured: {list(config.get('mcpServers', {}).keys())}")
            return True
        except json.JSONDecodeError as e:
            print(f"❌ {mcp_path} is not valid JSON: {e}")
            return False


def test_claude_sees_mcp(container_id: str = None) -> bool:
    """Test if Claude can see the MCP servers."""
    print("\nTesting Claude's MCP visibility...")
    
    test_prompt = """Please list all the MCP servers you have access to. 
Just output the server names, one per line."""
    
    if container_id:
        # Run claude in container
        result = subprocess.run(
            ["docker", "exec", container_id, "claude", "--output-format", "json", "-p", test_prompt],
            capture_output=True,
            text=True,
            timeout=30
        )
    else:
        # Run locally
        result = subprocess.run(
            ["claude", "--output-format", "json", "-p", test_prompt],
            capture_output=True,
            text=True,
            timeout=30
        )
    
    if result.returncode != 0:
        print(f"❌ Claude command failed: {result.stderr[:500]}")
        return False
    
    # Check if output mentions sourcegraph or MCP
    output = result.stdout + result.stderr
    if "sourcegraph" in output.lower():
        print("✅ Claude detected Sourcegraph MCP")
        return True
    elif "mcp" in output.lower():
        print("✅ Claude detected MCP servers")
        return True
    else:
        print("⚠️  Claude output doesn't clearly mention MCP servers")
        print(f"   Output snippet: {output[:200]}")
        return False


def main():
    """Main verification routine."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Verify Sourcegraph MCP setup")
    parser.add_argument("--container-id", help="Docker container ID to check")
    parser.add_argument("--test-claude", action="store_true", help="Test if Claude can see MCP")
    args = parser.parse_args()
    
    print("Verifying Sourcegraph MCP Configuration\n")
    print("=" * 50)
    
    # Check config file
    config_ok = check_mcp_config_file(args.container_id)
    
    if not config_ok:
        print("\n❌ MCP configuration not found")
        sys.exit(1)
    
    # Optionally test Claude
    if args.test_claude:
        try:
            claude_ok = test_claude_sees_mcp(args.container_id)
            if not claude_ok:
                print("\n⚠️  Claude MCP visibility uncertain")
                sys.exit(1)
        except subprocess.TimeoutExpired:
            print("\n⚠️  Claude test timed out")
            sys.exit(1)
        except Exception as e:
            print(f"\n⚠️  Claude test failed: {e}")
            sys.exit(1)
    
    print("\n" + "=" * 50)
    print("✅ MCP setup verification complete")
    sys.exit(0)


if __name__ == "__main__":
    main()
