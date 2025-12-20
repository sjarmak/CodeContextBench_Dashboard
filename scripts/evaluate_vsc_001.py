#!/usr/bin/env python3
"""
Detailed evaluation of big-code-vsc-001 task completion.

Analyzes:
1. Task requirements vs agent output
2. Code changes made
3. Tests status
4. Token efficiency
5. Cost analysis
6. Architecture understanding
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any
import anthropic

# Anthropic pricing (as of Dec 2024)
# Haiku: $0.80/M input, $4.00/M output tokens
HAIKU_INPUT_COST = 0.80 / 1_000_000
HAIKU_OUTPUT_COST = 4.00 / 1_000_000

def load_trajectory(path: Path) -> Dict[str, Any]:
    """Load and summarize trajectory."""
    with open(path) as f:
        traj = json.load(f)
    
    steps = traj.get("steps", [])
    metrics = traj.get("final_metrics", {})
    
    return {
        "steps": steps,
        "step_count": len(steps),
        "prompt_tokens": metrics.get("total_prompt_tokens", 0),
        "completion_tokens": metrics.get("total_completion_tokens", 0),
        "total_tokens": metrics.get("total_prompt_tokens", 0) + metrics.get("total_completion_tokens", 0),
        "cached_tokens": metrics.get("total_cached_tokens", 0),
    }

def calculate_cost(prompt_tokens: int, completion_tokens: int) -> float:
    """Calculate cost in USD for Haiku model."""
    return (prompt_tokens * HAIKU_INPUT_COST) + (completion_tokens * HAIKU_OUTPUT_COST)

def extract_key_info(trajectory: Dict[str, Any]) -> Dict[str, Any]:
    """Extract key information from trajectory steps."""
    steps = trajectory["steps"]
    
    # Look for file operations, test runs, code changes
    info = {
        "files_read": 0,
        "files_edited": 0,
        "tests_run": 0,
        "git_operations": 0,
        "errors_encountered": 0,
        "mcp_searches": 0,
        "key_actions": [],
    }
    
    for step in steps:
        msg = str(step.get("message", "")).lower()
        
        if any(x in msg for x in ["read", "open", "get file"]):
            info["files_read"] += 1
        if any(x in msg for x in ["edit", "write", "create", "modify"]):
            info["files_edited"] += 1
        if any(x in msg for x in ["test", "npm", "run tests"]):
            info["tests_run"] += 1
        if any(x in msg for x in ["git", "commit", "branch"]):
            info["git_operations"] += 1
        if any(x in msg for x in ["error", "failed", "exception"]):
            info["errors_encountered"] += 1
        if any(x in msg for x in ["sg_", "sourcegraph", "search"]):
            info["mcp_searches"] += 1
        
        # Track key actions
        if any(x in msg for x in ["added", "modified", "created", "fixed", "implemented"]):
            info["key_actions"].append(step.get("message", "")[:100])
    
    return info

def evaluate_with_claude(baseline_trajectory: Dict, mcp_trajectory: Dict, instruction: str) -> Dict:
    """Use Claude to evaluate quality."""
    
    baseline_info = extract_key_info(baseline_trajectory)
    mcp_info = extract_key_info(mcp_trajectory)
    
    prompt = f"""Evaluate these two agents' attempts to fix stale diagnostics in VS Code.

TASK REQUIREMENTS:
{instruction[:2000]}

=== BASELINE AGENT (Claude Code only) ===
Steps: {baseline_trajectory['step_count']}
Tokens: {baseline_trajectory['total_tokens']:,}
Files read: {baseline_info['files_read']}
Files edited: {baseline_info['files_edited']}
Tests run: {baseline_info['tests_run']}
Key actions: {len(baseline_info['key_actions'])}

=== MCP AGENT (Claude Code + Sourcegraph) ===
Steps: {mcp_trajectory['step_count']}
Tokens: {mcp_trajectory['total_tokens']:,}
Files read: {mcp_info['files_read']}
Files edited: {mcp_info['files_edited']}
Tests run: {mcp_info['tests_run']}
MCP searches used: {mcp_info['mcp_searches']}
Key actions: {len(mcp_info['key_actions'])}

EVALUATION:
For each agent, score (0-1.0):
1. Task Completion: Did they implement the fix? Find/edit necessary files? Make code changes?
2. Architecture Understanding: Did they understand the diagnostics pipeline (file watchers, extension host, problems panel)?
3. Test Coverage: Did they run tests? Check for regressions?
4. Efficiency: For tokens spent, how much actual progress was made?

Format as JSON:
{{
  "baseline": {{
    "completion": {{"score": 0.0, "reason": "..."}},
    "architecture": {{"score": 0.0, "reason": "..."}},
    "tests": {{"score": 0.0, "reason": "..."}},
    "efficiency": {{"score": 0.0, "reason": "..."}}
  }},
  "mcp": {{
    "completion": {{"score": 0.0, "reason": "..."}},
    "architecture": {{"score": 0.0, "reason": "..."}},
    "tests": {{"score": 0.0, "reason": "..."}},
    "efficiency": {{"score": 0.0, "reason": "..."}}
  }},
  "mcp_advantage": {{"area": "...", "explanation": "...", "magnitude": 0.0}}
}}"""

    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-opus-4-1-20250805",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )
    
    result_text = response.content[0].text
    start = result_text.find("{")
    end = result_text.rfind("}") + 1
    
    if start >= 0 and end > start:
        return json.loads(result_text[start:end])
    else:
        return {"error": "Could not parse response", "raw": result_text}

def main():
    """Evaluate vsc-001 task."""
    
    # Paths
    baseline_traj = Path("/Users/sjarmak/CodeContextBench/jobs/bigcode-comparison-20251220-1014/big-code-vsc-001/baseline")
    mcp_traj = Path("/Users/sjarmak/CodeContextBench/jobs/bigcode-comparison-20251220-1014/big-code-vsc-001/mcp")
    instruction_file = Path("/Users/sjarmak/CodeContextBench/benchmarks/big_code_mcp/big-code-vsc-001/instruction.md")
    
    # Find trajectory files
    baseline_file = list(baseline_traj.rglob("trajectory.json"))[0]
    mcp_file = list(mcp_traj.rglob("trajectory.json"))[0]
    
    with open(instruction_file) as f:
        instruction = f.read()
    
    # Load trajectories
    baseline_data = load_trajectory(baseline_file)
    mcp_data = load_trajectory(mcp_file)
    
    print("=" * 100)
    print("BIG CODE VSC-001: STALE DIAGNOSTICS FIX - EVALUATION")
    print("=" * 100)
    print()
    
    # Token analysis
    print("TOKEN USAGE ANALYSIS")
    print("-" * 100)
    baseline_cost = calculate_cost(baseline_data["prompt_tokens"], baseline_data["completion_tokens"])
    mcp_cost = calculate_cost(mcp_data["prompt_tokens"], mcp_data["completion_tokens"])
    
    print(f"Baseline (Claude Code only):")
    print(f"  Prompt tokens:  {baseline_data['prompt_tokens']:>10,}")
    print(f"  Completion:     {baseline_data['completion_tokens']:>10,}")
    print(f"  Total:          {baseline_data['total_tokens']:>10,}")
    print(f"  Steps:          {baseline_data['step_count']:>10}")
    print(f"  Cost:           ${baseline_cost:>10.4f}")
    print()
    
    print(f"MCP (Claude Code + Sourcegraph):")
    print(f"  Prompt tokens:  {mcp_data['prompt_tokens']:>10,}")
    print(f"  Completion:     {mcp_data['completion_tokens']:>10,}")
    print(f"  Total:          {mcp_data['total_tokens']:>10,}")
    print(f"  Steps:          {mcp_data['step_count']:>10}")
    print(f"  Cost:           ${mcp_cost:>10.4f}")
    print()
    
    delta_tokens = mcp_data["total_tokens"] - baseline_data["total_tokens"]
    delta_pct = (delta_tokens / baseline_data["total_tokens"] * 100)
    delta_cost = mcp_cost - baseline_cost
    delta_steps = mcp_data["step_count"] - baseline_data["step_count"]
    
    print(f"Difference:")
    print(f"  Tokens:         {delta_tokens:>10,} ({delta_pct:+.1f}%)")
    print(f"  Cost:           ${delta_cost:>10.4f} ({(delta_cost/baseline_cost*100):+.1f}%)")
    print(f"  Steps:          {delta_steps:>10,}")
    print()
    
    # Quality evaluation
    print("=" * 100)
    print("QUALITY EVALUATION (Using Claude Opus)")
    print("-" * 100)
    print("Evaluating: Task completion, architecture understanding, test coverage, efficiency...")
    print()
    
    eval_result = evaluate_with_claude(baseline_data, mcp_data, instruction)
    
    if "error" not in eval_result:
        # Display baseline scores
        baseline_scores = eval_result.get("baseline", {})
        print("BASELINE SCORES:")
        for criterion, data in baseline_scores.items():
            score = data.get("score", 0)
            reason = data.get("reason", "")
            print(f"  {criterion.replace('_', ' ').title():<20}: {score:.2f}/1.0")
            print(f"    {reason[:70]}...")
        print()
        
        # Display MCP scores
        mcp_scores = eval_result.get("mcp", {})
        print("MCP SCORES:")
        for criterion, data in mcp_scores.items():
            score = data.get("score", 0)
            reason = data.get("reason", "")
            print(f"  {criterion.replace('_', ' ').title():<20}: {score:.2f}/1.0")
            print(f"    {reason[:70]}...")
        print()
        
        # MCP advantage
        advantage = eval_result.get("mcp_advantage", {})
        if advantage:
            print("MCP ADVANTAGE:")
            print(f"  Area: {advantage.get('area')}")
            print(f"  Explanation: {advantage.get('explanation')}")
            print(f"  Magnitude: {advantage.get('magnitude', 0):.1f}x")
        print()
    else:
        print(f"Evaluation error: {eval_result.get('error')}")
        print()
    
    # Summary
    print("=" * 100)
    print("SUMMARY")
    print("=" * 100)
    print()
    print(f"MCP Cost Premium: ${delta_cost:.4f} ({delta_pct:+.1f}% more tokens)")
    print(f"MCP Value: {mcp_data['total_tokens'] / baseline_data['total_tokens']:.2f}x tokens spent")
    print()
    print("Key Question: Does 27% more spending (7.4M → 9.4M tokens) yield proportionally")
    print("              better architectural understanding and more complete solutions?")
    print()
    
    # Save detailed results
    results = {
        "task": "big-code-vsc-001",
        "baseline": baseline_data,
        "mcp": mcp_data,
        "cost_analysis": {
            "baseline_cost": baseline_cost,
            "mcp_cost": mcp_cost,
            "delta_cost": delta_cost,
            "delta_pct": delta_pct,
        },
        "evaluation": eval_result,
    }
    
    output_file = Path("vsc-001-evaluation.json")
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"Full evaluation saved to: {output_file}")

if __name__ == "__main__":
    main()
