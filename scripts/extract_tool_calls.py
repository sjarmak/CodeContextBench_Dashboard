#!/usr/bin/env python3
"""Extract and analyze tool calls from RepoQA agent trajectories."""

import json
import sys
from pathlib import Path
from collections import defaultdict

def analyze_trajectory(traj_path):
    """Analyze tool usage in a trajectory file."""
    with open(traj_path) as f:
        trajectory = json.load(f)
    
    task_id = trajectory.get("metadata", {}).get("task_id", "unknown")
    steps = trajectory.get("steps", [])
    
    tool_calls = defaultdict(int)
    total_steps = len(steps)
    
    for step in steps:
        action = step.get("action", {})
        if isinstance(action, dict):
            tool = action.get("tool")
            if tool:
                tool_calls[tool] += 1
    
    return {
        "task_id": task_id,
        "total_steps": total_steps,
        "tool_calls": dict(tool_calls),
        "unique_tools": len(tool_calls),
        "trajectory": trajectory
    }

def main():
    baseline_dir = Path(sys.argv[1])
    mcp_dir = Path(sys.argv[2])
    
    print("="*80)
    print("BASELINE AGENT TOOL USAGE")
    print("="*80)
    
    baseline_summaries = []
    for task_dir in sorted(baseline_dir.glob("requests-*")):
        traj_file = task_dir / "agent" / "trajectory.jsonl"
        if not traj_file.exists():
            print(f"  ⚠️  No trajectory: {task_dir.name}")
            continue
        
        with open(traj_file) as f:
            lines = f.readlines()
            if not lines:
                continue
            traj_json = json.loads(lines[-1])
        
        task_id = traj_json.get("metadata", {}).get("task_id", task_dir.name)
        steps = traj_json.get("steps", [])
        tool_calls = defaultdict(int)
        
        for step in steps:
            action = step.get("action", {})
            if isinstance(action, dict) and "tool" in action:
                tool_calls[action["tool"]] += 1
        
        score = 0
        for task_result_dir in baseline_dir.parent.glob("2025-12-20__21-56-32/requests-001-sr-qa*"):
            if task_dir.name.startswith("requests-001"):
                result_file = task_result_dir / "result.json"
                if result_file.exists():
                    with open(result_file) as f:
                        result = json.load(f)
                        score = result.get("verifier_result", {}).get("rewards", {}).get("score", 0)
                        break
        
        tools_str = ", ".join(f"{k}({v})" for k,v in sorted(tool_calls.items()))
        print(f"\n  {task_id}:")
        print(f"    Steps: {len(steps)}")
        print(f"    Tools: {tools_str if tools_str else '(none)'}")
        print(f"    Score: {score}")
        
        baseline_summaries.append({
            "task": task_id,
            "steps": len(steps),
            "tools": dict(tool_calls),
            "score": score
        })
    
    print("\n" + "="*80)
    print("MCP AGENT TOOL USAGE")
    print("="*80)
    
    mcp_summaries = []
    for task_dir in sorted(mcp_dir.glob("requests-*")):
        traj_file = task_dir / "agent" / "trajectory.jsonl"
        if not traj_file.exists():
            print(f"  ⚠️  No trajectory: {task_dir.name}")
            continue
        
        with open(traj_file) as f:
            lines = f.readlines()
            if not lines:
                continue
            traj_json = json.loads(lines[-1])
        
        task_id = traj_json.get("metadata", {}).get("task_id", task_dir.name)
        steps = traj_json.get("steps", [])
        tool_calls = defaultdict(int)
        deep_search_calls = 0
        
        for step in steps:
            action = step.get("action", {})
            if isinstance(action, dict) and "tool" in action:
                tool = action["tool"]
                tool_calls[tool] += 1
                # Count Sourcegraph deep search calls
                if tool in ["DeepSearch", "deep_search", "Bash"] and "deepsearch" in str(action).lower():
                    deep_search_calls += 1
        
        score = 0
        for task_result_dir in mcp_dir.parent.glob("2025-12-20__22-07-03/requests-*"):
            if task_dir.name.startswith(task_id.split("-")[0] + "-"):
                result_file = task_result_dir / "result.json"
                if result_file.exists():
                    with open(result_file) as f:
                        result = json.load(f)
                        score = result.get("verifier_result", {}).get("rewards", {}).get("score", 0)
                        break
        
        tools_str = ", ".join(f"{k}({v})" for k,v in sorted(tool_calls.items()))
        print(f"\n  {task_id}:")
        print(f"    Steps: {len(steps)}")
        print(f"    Tools: {tools_str if tools_str else '(none)'}")
        print(f"    Deep Search calls: {deep_search_calls}")
        print(f"    Score: {score}")
        
        mcp_summaries.append({
            "task": task_id,
            "steps": len(steps),
            "tools": dict(tool_calls),
            "score": score
        })
    
    # Summary comparison
    print("\n" + "="*80)
    print("SUMMARY COMPARISON")
    print("="*80)
    
    baseline_total_steps = sum(s["steps"] for s in baseline_summaries)
    baseline_total_tools = sum(sum(s["tools"].values()) for s in baseline_summaries)
    baseline_avg_score = sum(s["score"] for s in baseline_summaries) / len(baseline_summaries) if baseline_summaries else 0
    
    mcp_total_steps = sum(s["steps"] for s in mcp_summaries)
    mcp_total_tools = sum(sum(s["tools"].values()) for s in mcp_summaries)
    mcp_avg_score = sum(s["score"] for s in mcp_summaries) / len(mcp_summaries) if mcp_summaries else 0
    
    print(f"\nBaseline (claude-code only):")
    print(f"  Total steps: {baseline_total_steps} ({baseline_total_steps/len(baseline_summaries):.1f} per task)")
    print(f"  Total tool calls: {baseline_total_tools} ({baseline_total_tools/len(baseline_summaries):.1f} per task)")
    print(f"  Average score: {baseline_avg_score:.2f}")
    
    print(f"\nMCP (claude-code + Sourcegraph):")
    print(f"  Total steps: {mcp_total_steps} ({mcp_total_steps/len(mcp_summaries):.1f} per task)")
    print(f"  Total tool calls: {mcp_total_tools} ({mcp_total_tools/len(mcp_summaries):.1f} per task)")
    print(f"  Average score: {mcp_avg_score:.2f}")
    
    print(f"\nTool Usage Ratio:")
    ratio = mcp_total_tools / max(baseline_total_tools, 1)
    print(f"  MCP uses {ratio:.2f}x more tool calls than baseline")
    
    print(f"\nAccuracy Improvement:")
    if baseline_avg_score > 0:
        improvement = ((mcp_avg_score - baseline_avg_score) / baseline_avg_score) * 100
        print(f"  MCP: {improvement:+.1f}% vs baseline")
    else:
        print(f"  MCP: {mcp_avg_score:.2f} vs baseline 0.00 (cannot compute %)")

if __name__ == "__main__":
    main()
