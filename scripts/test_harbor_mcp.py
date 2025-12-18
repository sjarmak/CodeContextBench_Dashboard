#!/usr/bin/env python3
"""
Minimal test to verify MCP config works in Harbor environment.

This script:
1. Creates a minimal Harbor environment
2. Runs the agent setup
3. Verifies .mcp.json was created in /workspace
4. Checks if Claude Code can load the MCP config
"""
import asyncio
import os
import sys
import tempfile
from pathlib import Path

# Add parent directory to path to import agent
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.claude_sourcegraph_mcp_agent import ClaudeCodeSourcegraphMCPAgent


class MockHarborEnvironment:
    """Minimal mock of Harbor environment for testing."""

    def __init__(self, workspace_dir: Path):
        self.workspace_dir = workspace_dir
        self.uploaded_files = {}

    async def upload_file(self, source_path: Path, target_path: str):
        """Mock file upload - just copy to workspace."""
        with open(source_path, 'r') as f:
            content = f.read()

        # Store in our mock workspace
        self.uploaded_files[target_path] = content

        # Also write to actual workspace directory for verification
        target = self.workspace_dir / target_path.lstrip('/')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)

        print(f"   ✓ Uploaded: {target_path}")


async def main():
    print("=" * 70)
    print("Harbor MCP Integration Test")
    print("=" * 70)

    # Get credentials from environment
    sg_url = os.environ.get("SOURCEGRAPH_URL", "https://sourcegraph.sourcegraph.com")
    sg_token = os.environ.get("SOURCEGRAPH_ACCESS_TOKEN", "")

    if not sg_token:
        print("\n❌ Error: SOURCEGRAPH_ACCESS_TOKEN environment variable required")
        print("   Set it with: export SOURCEGRAPH_ACCESS_TOKEN=your_token")
        return 1

    print(f"\n📋 Configuration:")
    print(f"   SOURCEGRAPH_URL: {sg_url}")
    print(f"   SOURCEGRAPH_ACCESS_TOKEN: {sg_token[:20]}...")

    with tempfile.TemporaryDirectory() as tmpdir:
        logs_dir = Path(tmpdir) / "logs"
        workspace_dir = Path(tmpdir) / "workspace"
        logs_dir.mkdir()
        workspace_dir.mkdir()

        print(f"\n📁 Test directories:")
        print(f"   Logs: {logs_dir}")
        print(f"   Workspace: {workspace_dir}")

        # Create agent
        print(f"\n🤖 Creating ClaudeCodeSourcegraphMCPAgent...")
        agent = ClaudeCodeSourcegraphMCPAgent(logs_dir=logs_dir)

        # Create mock environment
        mock_env = MockHarborEnvironment(workspace_dir)

        # Run setup (this will create .mcp.json and CLAUDE.md)
        print(f"\n⚙️  Running agent.setup()...")

        # Mock the parent setup to avoid actual Claude Code installation
        original_setup = ClaudeCodeSourcegraphMCPAgent.__bases__[0].setup

        async def mock_parent_setup(self, env):
            print("   ✓ Skipped parent ClaudeCode.setup() (mock)")

        ClaudeCodeSourcegraphMCPAgent.__bases__[0].setup = mock_parent_setup

        try:
            await agent.setup(mock_env)
        finally:
            # Restore original
            ClaudeCodeSourcegraphMCPAgent.__bases__[0].setup = original_setup

        print(f"\n📝 Verifying uploaded files...")

        # Check .mcp.json
        mcp_json_path = workspace_dir / ".mcp.json"
        if not mcp_json_path.exists():
            print("   ❌ .mcp.json was not created!")
            return 1

        print(f"   ✓ .mcp.json exists")

        # Verify .mcp.json content
        import json
        with open(mcp_json_path) as f:
            mcp_config = json.load(f)

        if "mcpServers" not in mcp_config:
            print("   ❌ .mcp.json missing 'mcpServers'")
            return 1

        if "sourcegraph" not in mcp_config["mcpServers"]:
            print("   ❌ .mcp.json missing 'sourcegraph' server")
            return 1

        sg_config = mcp_config["mcpServers"]["sourcegraph"]

        if sg_config.get("type") != "http":
            print(f"   ❌ Wrong type: {sg_config.get('type')}")
            return 1

        expected_url = f"{sg_url}/.api/mcp/v1"
        if sg_config.get("url") != expected_url:
            print(f"   ❌ Wrong URL: {sg_config.get('url')}")
            print(f"      Expected: {expected_url}")
            return 1

        auth_header = sg_config.get("headers", {}).get("Authorization", "")
        if not auth_header.startswith("token "):
            print(f"   ❌ Wrong auth header: {auth_header}")
            return 1

        print(f"   ✓ .mcp.json has correct structure")
        print(f"   ✓ URL: {sg_config['url']}")
        print(f"   ✓ Auth: token {sg_token[:10]}...")

        # Check CLAUDE.md
        claude_md_path = workspace_dir / "CLAUDE.md"
        if not claude_md_path.exists():
            print("   ❌ CLAUDE.md was not created!")
            return 1

        print(f"   ✓ CLAUDE.md exists")

        claude_content = claude_md_path.read_text()
        if "Sourcegraph MCP" not in claude_content:
            print("   ❌ CLAUDE.md missing expected content")
            return 1

        print(f"   ✓ CLAUDE.md has Sourcegraph instructions")

        print(f"\n📄 Generated .mcp.json:")
        print("-" * 70)
        print(json.dumps(mcp_config, indent=2))
        print("-" * 70)

        print(f"\n✅ All checks passed!")
        print(f"\n💡 Next steps:")
        print(f"   1. The agent creates /workspace/.mcp.json during setup")
        print(f"   2. Claude Code will auto-discover this file")
        print(f"   3. MCP server should connect to: {expected_url}")

        return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))
