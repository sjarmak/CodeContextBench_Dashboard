#!/usr/bin/env python3
"""
Analyze RepoQA tool usage between baseline and MCP agents.

Measures:
- Tool calls made (MCP deep search vs baseline)
- Task accuracy (correct function found)
- Token efficiency
- Correctness by task type
"""

import json
import sys
from pathlib import Path
from collections import defaultdict
import statistics

def load_trajectories(agent_dir):
    """Load all trajectory.jsonl files from agent output directory."""
    trajectories = []
    for jsonl_file in Path(agent_dir).rglob("trajectory.jsonl"):
        with open(jsonl_file) as f:
            for line in f:
                if line.strip():
                    trajectories.append(json.loads(line))
    return trajectories

def count_tool_calls(trajectory):
    """Count tool calls in a trajectory."""
    tool_calls = defaultdict(int)
    if "steps" not in trajectory:
        return tool_calls
    
    for step in trajectory["steps"]:
        if "action" not in step:
            continue
        action = step["action"]
        if isinstance(action, dict) and "tool" in action:
            tool_calls[action["tool"]] += 1
    return tool_calls

def extract_task_metadata(trajectory):
    """Extract task metadata from trajectory."""
    if "metadata" in trajectory:
        meta = trajectory["metadata"]
        return {
            "task_id": meta.get("task_id"),
            "variant": meta.get("variant", "unknown"),
            "repository": meta.get("repository", ""),
            "function_description": meta.get("function_description", "")
        }
    return {}

def measure_accuracy(trajectory):
    """Measure if agent found correct function."""
    # Check if final answer matches expected output
    if "metadata" not in trajectory:
        return None
    
    meta = trajectory["metadata"]
    correct_name = meta.get("canonical_name")
    correct_path = meta.get("canonical_path")
    
    # Look for solution in trajectory
    solution = None
    for step in trajectory.get("steps", []):
        if "output" in step and isinstance(step["output"], dict):
            if "function_name" in step["output"]:
                solution = {
                    "name": step["output"].get("function_name"),
                    "path": step["output"].get("function_path")
                }
                break
    
    if not solution:
        return False
    
    # Check accuracy
    name_correct = solution.get("name") == correct_name
    path_correct = solution.get("path") == correct_path
    
    return name_correct and path_correct

def analyze_agent(agent_dir, agent_name):
    """Analyze all trajectories for an agent."""
    trajectories = load_trajectories(agent_dir)
    
    if not trajectories:
        print(f"⚠️  No trajectories found in {agent_dir}")
        return None
    
    print(f"\n{'='*70}")
    print(f"Agent: {agent_name}")
    print(f"{'='*70}")
    print(f"Total tasks: {len(trajectories)}")
    
    # Tool usage analysis
    all_tool_calls = defaultdict(int)
    all_steps = []
    token_usage = []
    accuracies = []
    
    for traj in trajectories:
        task_meta = extract_task_metadata(traj)
        tool_calls = count_tool_calls(traj)
        accuracy = measure_accuracy(traj)
        
        # Aggregate
        for tool, count in tool_calls.items():
            all_tool_calls[tool] += count
        all_steps.extend(traj.get("steps", []))
        
        if "metadata" in traj and "token_usage" in traj["metadata"]:
            token_usage.append(traj["metadata"]["token_usage"])
        
        if accuracy is not None:
            accuracies.append(accuracy)
        
        # Per-task debug
        print(f"\n  Task: {task_meta.get('task_id', 'unknown')}")
        print(f"    Tools: {dict(tool_calls)}")
        print(f"    Steps: {len(traj.get('steps', []))}")
        print(f"    Accuracy: {'✓ CORRECT' if accuracy else '✗ WRONG'}")
    
    # Summary statistics
    print(f"\n{'-'*70}")
    print(f"SUMMARY STATISTICS")
    print(f"{'-'*70}")
    
    print(f"\nTool Usage:")
    if all_tool_calls:
        for tool, count in sorted(all_tool_calls.items(), key=lambda x: -x[1]):
            print(f"  {tool}: {count} calls")
    else:
        print("  (no tool calls detected)")
    
    print(f"\nTask Metrics:")
    print(f"  Total steps: {len(all_steps)}")
    print(f"  Avg steps per task: {len(all_steps) / len(trajectories):.1f}")
    
    if token_usage:
        print(f"  Token usage:")
        print(f"    Total: {sum(token_usage):,}")
        print(f"    Avg per task: {statistics.mean(token_usage):,.0f}")
        print(f"    Min: {min(token_usage):,}")
        print(f"    Max: {max(token_usage):,}")
    
    if accuracies:
        accuracy_pct = (sum(accuracies) / len(accuracies)) * 100
        print(f"  Accuracy: {sum(accuracies)}/{len(accuracies)} ({accuracy_pct:.1f}%)")
    
    return {
        "name": agent_name,
        "tasks": len(trajectories),
        "tool_calls": dict(all_tool_calls),
        "total_steps": len(all_steps),
        "accuracy": (sum(accuracies) / len(accuracies)) if accuracies else 0,
        "total_tokens": sum(token_usage) if token_usage else 0
    }

def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <baseline_dir> <mcp_dir>")
        sys.exit(1)
    
    baseline_dir = sys.argv[1]
    mcp_dir = sys.argv[2]
    
    # Analyze both agents
    baseline = analyze_agent(baseline_dir, "Baseline (claude-code)")
    mcp = analyze_agent(mcp_dir, "MCP Agent (claude-code + Sourcegraph)")
    
    # Comparison
    if baseline and mcp:
        print(f"\n{'='*70}")
        print(f"COMPARISON: Baseline vs MCP")
        print(f"{'='*70}")
        
        print(f"\nTool Usage:")
        print(f"  Baseline tool calls: {sum(baseline['tool_calls'].values())}")
        print(f"  MCP tool calls: {sum(mcp['tool_calls'].values())}")
        if sum(mcp['tool_calls'].values()) > 0:
            ratio = sum(mcp['tool_calls'].values()) / max(sum(baseline['tool_calls'].values()), 1)
            print(f"  → MCP uses {ratio:.1f}x more tool calls")
        
        print(f"\nAccuracy:")
        print(f"  Baseline: {baseline['accuracy']*100:.1f}%")
        print(f"  MCP: {mcp['accuracy']*100:.1f}%")
        if mcp['accuracy'] > baseline['accuracy']:
            improvement = ((mcp['accuracy'] - baseline['accuracy']) / baseline['accuracy']) * 100
            print(f"  → MCP improves accuracy by {improvement:.1f}%")
        
        print(f"\nToken Efficiency:")
        baseline_tokens = baseline['total_tokens'] / max(baseline['tasks'], 1)
        mcp_tokens = mcp['total_tokens'] / max(mcp['tasks'], 1)
        print(f"  Baseline avg per task: {baseline_tokens:,.0f} tokens")
        print(f"  MCP avg per task: {mcp_tokens:,.0f} tokens")
        if mcp_tokens > baseline_tokens:
            ratio = mcp_tokens / baseline_tokens
            print(f"  → MCP uses {ratio:.2f}x tokens (higher = less efficient)")
        
        print(f"\nConclusion:")
        uses_mcp_tools = sum(mcp['tool_calls'].values()) > sum(baseline['tool_calls'].values())
        improves_accuracy = mcp['accuracy'] > baseline['accuracy']
        
        if uses_mcp_tools:
            print(f"  ✓ MCP agent DOES use Sourcegraph tools (not pattern matching)")
        else:
            print(f"  ✗ MCP agent does NOT use Sourcegraph tools")
        
        if improves_accuracy:
            print(f"  ✓ MCP improves task accuracy")
        else:
            print(f"  ✗ MCP does NOT improve accuracy")

if __name__ == "__main__":
    main()
