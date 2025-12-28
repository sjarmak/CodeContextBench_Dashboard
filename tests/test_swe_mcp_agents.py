#!/usr/bin/env python3
"""
Quick verification test for SWE-agent MCP variants.

Tests that all three agent classes can be instantiated and have correct MCP config.
"""
import json
import os
import sys
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

def test_agent_imports():
    """Test that all agent classes can be imported."""
    print("Testing agent imports...")
    try:
        from mini_swe_agent_mcp import (
            MiniSweAgentBaseline,
            MiniSweAgentSourcegraphMCP,
            MiniSweAgentDeepSearchMCP,
        )
        print("✓ All agent classes imported successfully")
        return True
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False


def test_baseline_agent():
    """Test baseline agent (no MCP)."""
    print("\nTesting MiniSweAgentBaseline (no MCP)...")
    from mini_swe_agent_mcp import MiniSweAgentBaseline

    logs_dir = Path("/tmp/test_baseline")
    logs_dir.mkdir(exist_ok=True, parents=True)

    try:
        agent = MiniSweAgentBaseline(logs_dir=logs_dir)

        # Check that no MCP servers are configured
        if not agent.mcp_servers:
            print("✓ Baseline agent has no MCP servers (correct)")
            return True
        else:
            print(f"✗ Baseline agent has MCP servers: {agent.mcp_servers}")
            return False
    except Exception as e:
        print(f"✗ Baseline agent instantiation failed: {e}")
        return False


def test_sourcegraph_mcp_agent():
    """Test Sourcegraph MCP agent."""
    print("\nTesting MiniSweAgentSourcegraphMCP...")
    from mini_swe_agent_mcp import MiniSweAgentSourcegraphMCP

    # Set up test environment
    os.environ["SOURCEGRAPH_URL"] = "https://sourcegraph.com"
    os.environ["SOURCEGRAPH_ACCESS_TOKEN"] = "test_token_123"

    logs_dir = Path("/tmp/test_sourcegraph_mcp")
    logs_dir.mkdir(exist_ok=True, parents=True)

    try:
        agent = MiniSweAgentSourcegraphMCP(logs_dir=logs_dir)

        # Check MCP config
        if "sourcegraph" not in agent.mcp_servers:
            print("✗ Sourcegraph MCP server not configured")
            return False

        sg_config = agent.mcp_servers["sourcegraph"]

        # Verify HTTP-based config
        if sg_config.get("type") != "http":
            print(f"✗ Expected HTTP MCP, got: {sg_config.get('type')}")
            return False

        expected_url = "https://sourcegraph.com/.api/mcp/v1"
        if sg_config.get("url") != expected_url:
            print(f"✗ Expected URL {expected_url}, got: {sg_config.get('url')}")
            return False

        if "Authorization" not in sg_config.get("headers", {}):
            print("✗ Authorization header not set")
            return False

        print("✓ Sourcegraph MCP agent configured correctly")
        print(f"  - Type: http")
        print(f"  - URL: {sg_config['url']}")
        print(f"  - Has auth header: yes")
        return True

    except Exception as e:
        print(f"✗ Sourcegraph MCP agent instantiation failed: {e}")
        return False


def test_deepsearch_mcp_agent():
    """Test Deep Search MCP agent."""
    print("\nTesting MiniSweAgentDeepSearchMCP...")
    from mini_swe_agent_mcp import MiniSweAgentDeepSearchMCP

    # Set up test environment
    os.environ["SOURCEGRAPH_URL"] = "https://sourcegraph.com"
    os.environ["SOURCEGRAPH_ACCESS_TOKEN"] = "test_token_123"

    logs_dir = Path("/tmp/test_deepsearch_mcp")
    logs_dir.mkdir(exist_ok=True, parents=True)

    try:
        agent = MiniSweAgentDeepSearchMCP(logs_dir=logs_dir)

        # Check MCP config
        if "deepsearch" not in agent.mcp_servers:
            print("✗ Deep Search MCP server not configured")
            return False

        ds_config = agent.mcp_servers["deepsearch"]

        # Verify HTTP-based config
        if ds_config.get("type") != "http":
            print(f"✗ Expected HTTP MCP, got: {ds_config.get('type')}")
            return False

        expected_url = "https://sourcegraph.com/.api/mcp/deepsearch"
        if ds_config.get("url") != expected_url:
            print(f"✗ Expected URL {expected_url}, got: {ds_config.get('url')}")
            return False

        if "Authorization" not in ds_config.get("headers", {}):
            print("✗ Authorization header not set")
            return False

        print("✓ Deep Search MCP agent configured correctly")
        print(f"  - Type: http")
        print(f"  - URL: {ds_config['url']}")
        print(f"  - Has auth header: yes")
        return True

    except Exception as e:
        print(f"✗ Deep Search MCP agent instantiation failed: {e}")
        return False


def test_http_mcp_config_generation():
    """Test that HTTP MCP config is generated correctly."""
    print("\nTesting HTTP MCP config file generation...")
    from mini_swe_agent_mcp import MiniSweAgentSourcegraphMCP

    os.environ["SOURCEGRAPH_URL"] = "https://sourcegraph.com"
    os.environ["SOURCEGRAPH_ACCESS_TOKEN"] = "test_token_123"

    logs_dir = Path("/tmp/test_http_config")
    logs_dir.mkdir(exist_ok=True, parents=True)

    try:
        agent = MiniSweAgentSourcegraphMCP(logs_dir=logs_dir)

        # Generate config command
        config_path = logs_dir / "test_mcp.json"
        cmd = agent._create_mcp_config_file(config_path)

        if not cmd:
            print("✗ No config command generated")
            return False

        # Execute command to create config
        os.system(cmd)

        # Read and verify config
        if not config_path.exists():
            print("✗ Config file not created")
            return False

        with open(config_path) as f:
            config = json.load(f)

        # Verify structure
        if "mcpServers" not in config:
            print("✗ mcpServers key missing")
            return False

        if "sourcegraph" not in config["mcpServers"]:
            print("✗ sourcegraph server missing")
            return False

        sg_server = config["mcpServers"]["sourcegraph"]

        if sg_server.get("type") != "http":
            print(f"✗ Wrong server type: {sg_server.get('type')}")
            return False

        print("✓ HTTP MCP config file generated correctly")
        print(f"  Config: {json.dumps(config, indent=2)}")
        return True

    except Exception as e:
        print(f"✗ Config generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("SWE-Agent MCP Variants - Verification Tests")
    print("=" * 60)

    tests = [
        ("Import Test", test_agent_imports),
        ("Baseline Agent", test_baseline_agent),
        ("Sourcegraph MCP Agent", test_sourcegraph_mcp_agent),
        ("Deep Search MCP Agent", test_deepsearch_mcp_agent),
        ("HTTP MCP Config Generation", test_http_mcp_config_generation),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"✗ {name} crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n✅ All tests passed! SWE-agent MCP setup is working correctly.")
        return 0
    else:
        print(f"\n❌ {total - passed} test(s) failed. Please review errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
