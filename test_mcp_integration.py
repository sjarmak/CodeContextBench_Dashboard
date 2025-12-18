#!/usr/bin/env python3
"""
Test that MCP configuration is created correctly by the agent.
Run with: uv run python test_mcp_integration.py
"""
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

# Import the agent
from agents.claude_sourcegraph_mcp_agent import ClaudeCodeSourcegraphMCPAgent


async def test_mcp_config():
    """Test that .mcp.json is created with correct format."""

    # Set test credentials
    os.environ["SOURCEGRAPH_URL"] = "https://sourcegraph.sourcegraph.com"
    os.environ["SOURCEGRAPH_ACCESS_TOKEN"] = "sgp_d1c0f3791ae0b441_e78121011997f6bd614cf33625f6ff7044a3e58b"

    with tempfile.TemporaryDirectory() as tmpdir:
        logs_dir = Path(tmpdir) / "logs"
        workspace_dir = Path(tmpdir) / "workspace"
        logs_dir.mkdir()
        workspace_dir.mkdir()

        print(f"📁 Test directories:")
        print(f"   Logs: {logs_dir}")
        print(f"   Workspace: {workspace_dir}")

        # Create agent
        print(f"\n🤖 Creating agent...")
        agent = ClaudeCodeSourcegraphMCPAgent(logs_dir=logs_dir)

        # Mock environment that saves files to workspace_dir
        mock_env = AsyncMock()

        uploaded_files = {}

        async def mock_upload(source_path, target_path):
            """Mock upload that copies to workspace."""
            content = Path(source_path).read_text()
            target = workspace_dir / target_path.lstrip('/')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
            uploaded_files[target_path] = content
            print(f"   ✓ Uploaded: {target_path}")

        mock_env.upload_file = mock_upload

        # Mock parent setup to skip Claude Code installation
        from harbor.agents.installed.claude_code import ClaudeCode
        original_setup = ClaudeCode.setup

        async def skip_setup(self, env):
            print("   ✓ Skipped parent setup")

        ClaudeCode.setup = skip_setup

        try:
            print(f"\n⚙️  Running setup...")
            await agent.setup(mock_env)
        finally:
            ClaudeCode.setup = original_setup

        # Verify files
        print(f"\n📝 Verifying files...")

        # Check .mcp.json
        mcp_json = workspace_dir / ".mcp.json"
        if not mcp_json.exists():
            print("   ❌ .mcp.json not created!")
            return False

        with open(mcp_json) as f:
            config = json.load(f)

        print(f"   ✓ .mcp.json exists")

        # Validate structure
        assert "mcpServers" in config, "Missing mcpServers"
        assert "sourcegraph" in config["mcpServers"], "Missing sourcegraph"

        sg = config["mcpServers"]["sourcegraph"]
        assert sg["type"] == "http", f"Wrong type: {sg.get('type')}"
        assert sg["url"] == "https://sourcegraph.sourcegraph.com/.api/mcp/v1", f"Wrong URL: {sg.get('url')}"
        assert sg["headers"]["Authorization"].startswith("token "), "Wrong auth"

        print(f"   ✓ Structure is valid")

        # Check CLAUDE.md
        claude_md = workspace_dir / "CLAUDE.md"
        if not claude_md.exists():
            print("   ❌ CLAUDE.md not created!")
            return False

        print(f"   ✓ CLAUDE.md exists")

        # Print config
        print(f"\n📋 Generated .mcp.json:")
        print("-" * 70)
        print(json.dumps(config, indent=2))
        print("-" * 70)

        print(f"\n✅ All tests passed!")
        return True


if __name__ == "__main__":
    try:
        success = asyncio.run(test_mcp_config())
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
