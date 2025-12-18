#!/bin/bash
# Quick test: Show the actual command that will run with MCP

set -e

source .venv-harbor/bin/activate

python3 << 'PYTHON'
import os
import tempfile
from pathlib import Path
from agents.claude_code_mcp_harbor import ClaudeCodeMCP

# Set test env vars
os.environ["SRC_ACCESS_TOKEN"] = "sgp_test123456"
os.environ["SOURCEGRAPH_MCP_URL"] = "https://sourcegraph.sourcegraph.com/.api/mcp/v1"

with tempfile.TemporaryDirectory() as tmpdir:
    logs_dir = Path(tmpdir)
    agent = ClaudeCodeMCP(logs_dir=logs_dir)
    
    instruction = "Fix the bug in src/utils.py"
    commands = agent.create_run_agent_commands(instruction)
    
    cmd = commands[0]
    
    print("=" * 80)
    print("COMMAND THAT WILL RUN:")
    print("=" * 80)
    print(cmd.command[:1000])
    print("\n... (truncated for brevity)")
    
    print("\n" + "=" * 80)
    print("KEY COMPONENTS PRESENT:")
    print("=" * 80)
    
    checks = [
        ("Setup MCP config", ".mcp.json" in cmd.command),
        ("Sourcegraph MCP", "sourcegraph" in cmd.command),
        ("MCP server config", "mcpServers" in cmd.command),
        ("Authorization header", "Authorization" in cmd.command),
        ("Claude Code execution", "claude -p" in cmd.command),
        ("JSON output format", "--output-format json" in cmd.command),
    ]
    
    for check_name, result in checks:
        status = "✓" if result else "✗"
        print(f"{status} {check_name}")
    
    print("\n" + "=" * 80)
    print("ENVIRONMENT VARIABLES:")
    print("=" * 80)
    if cmd.env:
        for k, v in sorted(cmd.env.items()):
            if "TOKEN" in k or "URL" in k or "ANTHROPIC" in k:
                # Show actual values for demo
                print(f"  {k}: {v}")
    
    print("\n" + "=" * 80)
    print("✓ Ready to run with Harbor!")
    print("=" * 80)

PYTHON
