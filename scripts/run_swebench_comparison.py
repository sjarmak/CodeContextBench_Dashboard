#!/usr/bin/env python3
"""
Run SWEBench MCP comparison experiment.

Executes 5 selected SWEBench tasks against 4 agent variants:
1. Baseline (no MCP)
2. Deep Search Focused (MCP + Deep Search)
3. MCP No Deep Search (MCP keyword/NLS only)
4. Full Toolkit (MCP all tools, neutral prompting)
"""

import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime
import time

# Configuration
BENCHMARK_PATH = "benchmarks/big_code_mcp/big-code-vsc-001"
MODEL = "anthropic/claude-haiku-4-5-20251001"

AGENTS = [
    {
        "name": "baseline",
        "display": "Baseline (No MCP)",
        "import_path": "agents.claude_baseline_agent:BaselineClaudeCodeAgent"
    },
    {
        "name": "deep_search_focused",
        "display": "Deep Search Focused",
        "import_path": "agents.mcp_variants:DeepSearchFocusedAgent"
    },
    {
        "name": "mcp_no_deep_search",
        "display": "MCP No Deep Search",
        "import_path": "agents.mcp_variants:MCPNonDeepSearchAgent"
    },
    {
        "name": "full_toolkit",
        "display": "Full Toolkit",
        "import_path": "agents.mcp_variants:FullToolkitAgent"
    }
]

TASKS = [
    "django__django-11119",
    "django__django-11532",
    "django__django-12143",
    "matplotlib__matplotlib-20859",
    "astropy__astropy-12907"
]

def run_harbor(agent_spec, task_name=None):
    """Run harbor with specified agent."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    
    cmd = [
        "harbor", "run",
        "--path", BENCHMARK_PATH,
        "--agent-import-path", agent_spec["import_path"],
        "--model", MODEL,
        "-n", "1",
        "--timeout-multiplier", "2.0"
    ]
    
    print(f"\n{'='*60}")
    print(f"Running: {agent_spec['display']}")
    print(f"Command: {' '.join(cmd)}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour timeout
        )
        
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "timestamp": timestamp
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Timeout after 1 hour",
            "timestamp": timestamp
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "timestamp": timestamp
        }

def main():
    results_dir = Path("results") / f"swebench_comparison_{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    results_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\nStarting SWEBench MCP Comparison Experiment")
    print(f"Results directory: {results_dir}")
    print(f"Agents: {len(AGENTS)}")
    print(f"Benchmark: {BENCHMARK_PATH}")
    
    all_results = {}
    
    for agent in AGENTS:
        agent_name = agent["name"]
        print(f"\n[{datetime.now().isoformat()}] Starting {agent['display']}...")
        
        result = run_harbor(agent)
        all_results[agent_name] = result
        
        # Save individual result
        result_file = results_dir / f"{agent_name}.json"
        with open(result_file, 'w') as f:
            # Don't dump stdout/stderr to avoid huge files
            summary = {
                "agent": agent_name,
                "display": agent["display"],
                "success": result.get("success"),
                "returncode": result.get("returncode"),
                "error": result.get("error"),
                "timestamp": result.get("timestamp")
            }
            json.dump(summary, f, indent=2)
        
        # Save full logs
        if "stdout" in result:
            log_file = results_dir / f"{agent_name}_stdout.log"
            log_file.write_text(result["stdout"])
        
        if "stderr" in result:
            err_file = results_dir / f"{agent_name}_stderr.log"
            err_file.write_text(result["stderr"])
        
        status = "✓" if result.get("success") else "✗"
        print(f"[{status}] {agent['display']}: {'SUCCESS' if result.get('success') else 'FAILED'}")
    
    # Create summary
    summary_file = results_dir / "summary.json"
    summary = {
        "experiment": "swebench_mcp_comparison",
        "timestamp": datetime.now().isoformat(),
        "benchmark": BENCHMARK_PATH,
        "model": MODEL,
        "agents": [
            {
                "name": agent["name"],
                "display": agent["display"],
                "success": all_results[agent["name"]].get("success")
            }
            for agent in AGENTS
        ],
        "results_dir": str(results_dir)
    }
    
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"\n{'='*60}")
    print("Experiment Complete")
    print(f"{'='*60}")
    print(f"Results saved to: {results_dir}")
    print(f"\nSummary:")
    for agent in AGENTS:
        result = all_results[agent["name"]]
        status = "✓ SUCCESS" if result.get("success") else "✗ FAILED"
        print(f"  {agent['display']:<30} {status}")
    
    return 0 if all(r.get("success") for r in all_results.values()) else 1

if __name__ == "__main__":
    sys.exit(main())
