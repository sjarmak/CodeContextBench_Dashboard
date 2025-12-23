#!/usr/bin/env python3
"""
Run all 4 agents against all 4 big_code tasks.

Tests:
- 4 agents (Baseline, Deep Search, No Deep Search, Full Toolkit)
- 4 tasks (K8s, Servo, TensorRT, VS Code)
= 16 total runs

Collects metrics on tokens, time, tools, and success rates.
"""

import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime
import time

BENCHMARK_PATHS = [
    "benchmarks/big_code_mcp/big-code-k8s-001",
    "benchmarks/big_code_mcp/big-code-servo-001",
    "benchmarks/big_code_mcp/big-code-trt-001",
    "benchmarks/big_code_mcp/big-code-vsc-001",
]

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

def get_task_name(path):
    """Extract task name from path."""
    return Path(path).name

def run_harbor(benchmark_path, agent_spec):
    """Run harbor with specified agent on specified benchmark."""
    cmd = [
        "harbor", "run",
        "--path", benchmark_path,
        "--agent-import-path", agent_spec["import_path"],
        "--model", "anthropic/claude-haiku-4-5-20251001",
        "-n", "1",
        "--timeout-multiplier", "2.0"
    ]
    
    print(f"  Running {agent_spec['display']}...", end=" ", flush=True)
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600
        )
        
        success = result.returncode == 0
        print(f"{'✓' if success else '✗'}")
        
        return {
            "success": success,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "timestamp": datetime.now().isoformat()
        }
    except subprocess.TimeoutExpired:
        print("✗ (timeout)")
        return {
            "success": False,
            "error": "Timeout after 1 hour",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        print(f"✗ ({str(e)[:30]})")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

def main():
    results_dir = Path("results") / f"bigcode_all_tasks_{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    results_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n{'='*80}")
    print("BIG CODE MULTI-TASK COMPARISON EXPERIMENT")
    print(f"{'='*80}")
    print(f"Results directory: {results_dir}")
    print(f"Tasks: {len(BENCHMARK_PATHS)}")
    print(f"Agents: {len(AGENTS)}")
    print(f"Total runs: {len(BENCHMARK_PATHS) * len(AGENTS)}")
    print()
    
    all_results = {}
    task_results = {}
    
    for benchmark_path in BENCHMARK_PATHS:
        task_name = get_task_name(benchmark_path)
        task_results[task_name] = {}
        
        print(f"\n{'─'*80}")
        print(f"Task: {task_name}")
        print(f"{'─'*80}")
        
        for agent in AGENTS:
            agent_name = agent["name"]
            result = run_harbor(benchmark_path, agent)
            
            # Store result
            result_key = f"{task_name}_{agent_name}"
            all_results[result_key] = result
            task_results[task_name][agent_name] = result.get("success", False)
            
            # Save logs
            if "stdout" in result:
                log_file = results_dir / f"{task_name}_{agent_name}_stdout.log"
                log_file.write_text(result["stdout"])
            
            if "stderr" in result:
                err_file = results_dir / f"{task_name}_{agent_name}_stderr.log"
                err_file.write_text(result["stderr"])
    
    # Create summary
    print(f"\n\n{'='*80}")
    print("RESULTS SUMMARY")
    print(f"{'='*80}\n")
    
    # Task summary table
    print(f"{'Task':<25} {'Baseline':<12} {'Deep Search':<12} {'No Deep Search':<12} {'Full Toolkit':<12} {'Success':<10}")
    print("─" * 80)
    
    summary_data = {
        "experiment": "bigcode_all_tasks",
        "timestamp": datetime.now().isoformat(),
        "results_dir": str(results_dir),
        "benchmarks": [],
        "per_task": {},
        "per_agent": {}
    }
    
    for task_name in sorted(task_results.keys()):
        results = task_results[task_name]
        successes = sum(1 for v in results.values() if v)
        
        row = f"{task_name:<25} "
        for agent in AGENTS:
            status = "✓ PASS" if results.get(agent["name"]) else "✗ FAIL"
            row += f"{status:<12} "
        row += f"{successes}/4"
        
        print(row)
        
        summary_data["per_task"][task_name] = {
            "results": results,
            "success_count": successes
        }
    
    # Agent summary
    print(f"\n{'─'*80}")
    print(f"{'AGENT':<25} {'K8s':<8} {'Servo':<8} {'TensorRT':<8} {'VS Code':<8} {'Total':<8}")
    print("─" * 80)
    
    for agent in AGENTS:
        row = f"{agent['display']:<25} "
        successes = 0
        for task_name in sorted(task_results.keys()):
            success = task_results[task_name].get(agent["name"], False)
            status = "✓" if success else "✗"
            row += f"{status:<8} "
            successes += 1 if success else 0
        
        row += f"{successes}/4"
        print(row)
        
        summary_data["per_agent"][agent["name"]] = {
            "display": agent["display"],
            "success_count": successes,
            "success_rate": (successes / len(BENCHMARK_PATHS)) * 100
        }
    
    # Overall stats
    total_successes = sum(
        sum(1 for v in results.values() if v)
        for results in task_results.values()
    )
    total_runs = len(BENCHMARK_PATHS) * len(AGENTS)
    
    print(f"\n{'─'*80}")
    print(f"Overall Success Rate: {total_successes}/{total_runs} ({(total_successes/total_runs)*100:.1f}%)")
    
    summary_data["overall"] = {
        "total_runs": total_runs,
        "successful": total_successes,
        "success_rate": (total_successes / total_runs) * 100
    }
    
    # Save summary
    summary_file = results_dir / "summary.json"
    with open(summary_file, 'w') as f:
        json.dump(summary_data, f, indent=2)
    
    print(f"\nSummary saved: {summary_file}")
    print(f"{'='*80}\n")
    
    return 0 if total_successes == total_runs else 1

if __name__ == "__main__":
    sys.exit(main())
