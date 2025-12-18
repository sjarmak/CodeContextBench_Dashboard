#!/usr/bin/env python3
"""
Test MCP connectivity inside a Harbor task environment.

This script:
1. Runs a single simple task with the MCP agent
2. Captures the network test output from the agent setup
3. Reports whether network connectivity exists
4. Shows detailed diagnostics from Claude's MCP initialization

Usage:
    export SOURCEGRAPH_URL=https://sourcegraph.sourcegraph.com
    export SOURCEGRAPH_ACCESS_TOKEN=your-token
    python runners/test_mcp_in_harbor.py
"""
import json
import subprocess
import sys
from pathlib import Path


def run_harbor_test():
    """Run a simple Harbor job with MCP agent to test network connectivity."""
    
    print("=" * 80)
    print("Testing MCP in Harbor Environment")
    print("=" * 80)
    
    benchmark_dir = Path("/Users/sjarmak/CodeContextBench/benchmarks/github_mined")
    
    print(f"\n📝 Using existing benchmark: github_mined")
    print(f"   Task: sgt-001 (single network connectivity test)")
    print(f"   Purpose: Run MCP agent to see network test output in Harbor")
    
    # Run Harbor with MCP agent - use only sgt-001
    cmd = [
        "harbor", "run",
        "--path", str(benchmark_dir),
        "--task-name", "sgt-001",
        "--agent-import-path", "agents.claude_sourcegraph_mcp_agent:ClaudeCodeSourcegraphMCPAgent",
        "--model", "anthropic/claude-3-5-sonnet-20241022",
        "-n", "1",
        "--jobs-dir", "jobs/mcp-network-test"
    ]
    
    print(f"\n🚀 Running Harbor command:")
    print(f"   {' '.join(cmd)}")
    print()
    
    try:
        result = subprocess.run(
            cmd,
            cwd="/Users/sjarmak/CodeContextBench",
            capture_output=False,
            text=True,
            timeout=600
        )
        
        if result.returncode == 0:
            print("\n✅ Harbor job completed")
        else:
            print(f"\n❌ Harbor job failed with code {result.returncode}")
        
        return result.returncode
    except subprocess.TimeoutExpired:
        print("\n❌ Harbor job timed out (10 minutes)")
        return 1
    except Exception as e:
        print(f"\n❌ Error running Harbor: {e}")
        return 1


def check_logs():
    """Check the agent logs for network test output."""
    print("\n" + "=" * 80)
    print("Checking Agent Logs")
    print("=" * 80)
    
    # Find the job directory
    jobs_dir = Path("/Users/sjarmak/CodeContextBench/jobs/mcp-network-test")
    if not jobs_dir.exists():
        print("⚠️  Job directory not found yet")
        return
    
    # Find agent logs
    agent_dirs = list(jobs_dir.glob("*/*/agent"))
    if not agent_dirs:
        print("⚠️  No agent logs found")
        return
    
    agent_dir = agent_dirs[0]
    print(f"\n📁 Agent directory: {agent_dir}")
    
    # List log files
    log_files = list(agent_dir.glob("*.log")) + list(agent_dir.glob("*.txt"))
    if not log_files:
        print("⚠️  No log files found")
        return
    
    print(f"\n📋 Found {len(log_files)} log files:")
    for log_file in log_files:
        print(f"   • {log_file.name}")
    
    # Look for network test output
    print("\n🔍 Searching for network test output...")
    for log_file in log_files:
        try:
            content = log_file.read_text()
            if "Network Test" in content or "network_test" in content or "sourcegraph" in content.lower():
                print(f"\n  Found in {log_file.name}:")
                print("  " + "-" * 76)
                
                # Extract relevant lines
                lines = content.split('\n')
                in_network_test = False
                for line in lines:
                    if "Network" in line or "network" in line or "sourcegraph" in line.lower():
                        in_network_test = True
                    if in_network_test:
                        print(f"  {line[:76]}")
                        if "===" in line and in_network_test and "Network" not in line:
                            break
        except Exception as e:
            pass


if __name__ == "__main__":
    code = run_harbor_test()
    check_logs()
    sys.exit(code)
