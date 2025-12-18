#!/usr/bin/env python3
"""
Standalone script to verify MCP configuration without Harbor dependencies.

This creates the .mcp.json file exactly as the agent would and verifies its format.
"""
import json
import os
from pathlib import Path


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


def verify_mcp_config(config: dict) -> list[str]:
    """Verify MCP config is valid. Returns list of errors (empty if valid)."""
    errors = []

    if "mcpServers" not in config:
        errors.append("Missing 'mcpServers' key")
        return errors

    if "sourcegraph" not in config["mcpServers"]:
        errors.append("Missing 'sourcegraph' server config")
        return errors

    sg_config = config["mcpServers"]["sourcegraph"]

    # Check required fields
    if sg_config.get("type") != "http":
        errors.append(f"Invalid type: {sg_config.get('type')}, expected 'http'")

    if "url" not in sg_config:
        errors.append("Missing 'url' field")
    elif not sg_config["url"].endswith("/.api/mcp/v1"):
        errors.append(f"URL should end with '/.api/mcp/v1': {sg_config['url']}")

    if "headers" not in sg_config:
        errors.append("Missing 'headers' field")
    elif "Authorization" not in sg_config["headers"]:
        errors.append("Missing 'Authorization' header")
    elif not sg_config["headers"]["Authorization"].startswith("token "):
        errors.append("Authorization should start with 'token '")

    return errors


def main():
    print("=" * 70)
    print("MCP Configuration Verification")
    print("=" * 70)

    # Get credentials from environment
    sg_url = os.environ.get("SOURCEGRAPH_URL", "")
    sg_token = os.environ.get("SOURCEGRAPH_ACCESS_TOKEN", "")

    if not sg_url:
        sg_url = input("Enter SOURCEGRAPH_URL (e.g., https://sourcegraph.sourcegraph.com): ").strip()
    if not sg_token:
        sg_token = input("Enter SOURCEGRAPH_ACCESS_TOKEN: ").strip()

    if not (sg_url and sg_token):
        print("❌ Error: Both SOURCEGRAPH_URL and SOURCEGRAPH_ACCESS_TOKEN are required")
        return 1

    print(f"\n📝 Creating MCP config...")
    print(f"   URL: {sg_url}")
    print(f"   Token: {sg_token[:20]}..." if len(sg_token) > 20 else f"   Token: {sg_token}")

    # Create config
    config = create_mcp_config(sg_url, sg_token)

    # Verify config
    errors = verify_mcp_config(config)

    if errors:
        print(f"\n❌ Configuration has {len(errors)} error(s):")
        for error in errors:
            print(f"   - {error}")
        return 1

    print("\n✅ Configuration is valid!")

    # Show the config
    print("\n📋 Generated .mcp.json:")
    print("-" * 70)
    print(json.dumps(config, indent=2))
    print("-" * 70)

    # Test URL construction
    expected_mcp_url = config["mcpServers"]["sourcegraph"]["url"]
    print(f"\n🔗 MCP Endpoint: {expected_mcp_url}")

    # Save to file
    output_path = Path("test_.mcp.json")
    with open(output_path, "w") as f:
        json.dump(config, f, indent=2)

    print(f"\n💾 Config saved to: {output_path.absolute()}")
    print("\n✨ Verification complete!")

    return 0


if __name__ == "__main__":
    exit(main())
