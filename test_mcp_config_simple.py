#!/usr/bin/env python3
"""
Simple test to verify MCP config generation logic.
This doesn't require Harbor to be importable.
"""
import json
import os

def create_mcp_config(sg_url: str, sg_token: str) -> dict:
    """Create MCP config exactly as the agent does."""
    # Ensure URL has protocol
    if not sg_url.startswith(('http://', 'https://')):
        sg_url = f"https://{sg_url}"

    # Ensure URL doesn't end with trailing slash
    sg_url = sg_url.rstrip('/')

    # Create MCP config for HTTP transport
    return {
        "mcpServers": {
            "sourcegraph": {
                "type": "http",
                "url": f"{sg_url}/.api/mcp/v1",
                "headers": {
                    "Authorization": f"token {sg_token}"
                }
            }
        }
    }


def main():
    print("=" * 70)
    print("MCP Configuration Test")
    print("=" * 70)

    # Get credentials
    sg_url = os.environ.get("SOURCEGRAPH_URL", "https://sourcegraph.sourcegraph.com")
    sg_token = os.environ.get("SOURCEGRAPH_ACCESS_TOKEN", "sgp_test")

    print(f"\n📋 Input:")
    print(f"   SOURCEGRAPH_URL: {sg_url}")
    print(f"   SOURCEGRAPH_ACCESS_TOKEN: {sg_token[:20]}...")

    # Generate config
    config = create_mcp_config(sg_url, sg_token)

    print(f"\n📄 Generated .mcp.json:")
    print("-" * 70)
    print(json.dumps(config, indent=2))
    print("-" * 70)

    # Validate
    sg_config = config["mcpServers"]["sourcegraph"]

    checks = [
        ("Type is 'http'", sg_config["type"] == "http"),
        ("URL ends with /.api/mcp/v1", sg_config["url"].endswith("/.api/mcp/v1")),
        ("Has Authorization header", "Authorization" in sg_config["headers"]),
        ("Auth starts with 'token '", sg_config["headers"]["Authorization"].startswith("token ")),
    ]

    print(f"\n✓ Validation:")
    all_passed = True
    for check_name, passed in checks:
        status = "✓" if passed else "✗"
        print(f"   {status} {check_name}")
        if not passed:
            all_passed = False

    if all_passed:
        print(f"\n✅ All checks passed!")
        print(f"\n💡 This config will be written to /workspace/.mcp.json")
        print(f"   Claude Code will auto-discover it and connect to:")
        print(f"   {sg_config['url']}")
        return 0
    else:
        print(f"\n❌ Some checks failed!")
        return 1


if __name__ == "__main__":
    exit(main())
