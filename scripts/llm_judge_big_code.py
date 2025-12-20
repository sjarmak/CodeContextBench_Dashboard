#!/usr/bin/env python3
"""
LLM-based judge for big code task quality evaluation.

Evaluates Claude's output against reward criteria:
1. Tests Pass (50% weight) - Did tests run successfully?
2. Code Changes Made (30% weight) - Were actual code changes implemented?
3. Architecture Understanding (20% weight) - Does solution show understanding of full system?
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any
import anthropic

def extract_trajectory_info(trajectory_path: Path) -> Dict[str, Any]:
    """Extract relevant info from trajectory for evaluation."""
    with open(trajectory_path) as f:
        traj = json.load(f)
    
    steps = traj.get("steps", [])
    final_metrics = traj.get("final_metrics", {})
    
    # Collect all messages/actions
    messages = []
    for step in steps:
        msg = step.get("message", "")
        if msg:
            messages.append(msg)
    
    return {
        "total_steps": len(steps),
        "prompt_tokens": final_metrics.get("total_prompt_tokens", 0),
        "completion_tokens": final_metrics.get("total_completion_tokens", 0),
        "messages": messages,
        "last_messages": messages[-10:] if messages else [],  # Last 10 msgs
    }


def judge_quality(
    task_name: str,
    baseline_trajectory: Path,
    mcp_trajectory: Path,
    task_instruction: Path,
) -> Dict[str, Any]:
    """Use Claude to judge quality of outputs."""
    
    # Load trajectories
    baseline_info = extract_trajectory_info(baseline_trajectory)
    mcp_info = extract_trajectory_info(mcp_trajectory)
    
    # Load task instruction
    with open(task_instruction) as f:
        instruction = f.read()
    
    # Create evaluation prompt
    eval_prompt = f"""You are an expert code reviewer evaluating two agents' attempts at a challenging coding task.

TASK: {task_name}

TASK DESCRIPTION:
{instruction[:2000]}

=== BASELINE AGENT OUTPUT ===
Steps taken: {baseline_info['total_steps']}
Tokens used: {baseline_info['prompt_tokens']:,}
Final actions (last 10 messages):
{chr(10).join(baseline_info['last_messages'])}

=== MCP AGENT OUTPUT ===
Steps taken: {mcp_info['total_steps']}
Tokens used: {mcp_info['prompt_tokens']:,}
Final actions (last 10 messages):
{chr(10).join(mcp_info['last_messages'])}

EVALUATION CRITERIA:
1. Tests Pass (50%): Did the agent write/modify code that would pass tests?
2. Code Changes (30%): Did the agent make actual code modifications (not just analysis)?
3. Architecture Understanding (20%): Does the solution show understanding of the full system architecture?

Evaluate each agent on these criteria. For each criterion, provide:
- Score (0.0-1.0)
- Reasoning
- Evidence from the trajectory

Format as JSON:
{{
  "baseline": {{
    "tests_pass": {{"score": 0.0, "reasoning": "..."}},
    "code_changes": {{"score": 0.0, "reasoning": "..."}},
    "architecture": {{"score": 0.0, "reasoning": "..."}},
    "overall": 0.0
  }},
  "mcp": {{
    "tests_pass": {{"score": 0.0, "reasoning": "..."}},
    "code_changes": {{"score": 0.0, "reasoning": "..."}},
    "architecture": {{"score": 0.0, "reasoning": "..."}},
    "overall": 0.0
  }},
  "mcp_advantage": {{"category": "...", "explanation": "..."}}
}}"""

    # Call Claude
    import os
    client = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))
    response = client.messages.create(
        model="claude-opus-4-1-20250805",
        max_tokens=2000,
        messages=[{"role": "user", "content": eval_prompt}]
    )
    
    # Parse response
    try:
        result_text = response.content[0].text
        # Extract JSON from response
        start = result_text.find("{")
        end = result_text.rfind("}") + 1
        if start >= 0 and end > start:
            result = json.loads(result_text[start:end])
        else:
            result = {"error": "Could not parse JSON from response", "raw": result_text}
    except Exception as e:
        result = {"error": str(e), "raw": result_text}
    
    return {
        "task": task_name,
        "baseline_tokens": baseline_info["prompt_tokens"],
        "mcp_tokens": mcp_info["prompt_tokens"],
        "evaluation": result,
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: llm_judge_big_code.py <comparison_dir>")
        print()
        print("Example:")
        print("  python llm_judge_big_code.py jobs/bigcode-comparison-20251220-1014")
        sys.exit(1)
    
    comparison_dir = Path(sys.argv[1])
    
    if not comparison_dir.exists():
        print(f"ERROR: Directory not found: {comparison_dir}")
        sys.exit(1)
    
    # Find all tasks
    tasks = sorted([d for d in comparison_dir.iterdir() if d.is_dir() and d.name.startswith("big-code-")])
    
    if not tasks:
        print(f"ERROR: No big-code-* tasks found in {comparison_dir}")
        sys.exit(1)
    
    print("=" * 120)
    print("BIG CODE MCP QUALITY EVALUATION (LLM JUDGE)")
    print("=" * 120)
    print()
    
    all_results = []
    
    for task_dir in tasks:
        task_name = task_dir.name
        
        # Find trajectories
        baseline_traj = None
        mcp_traj = None
        
        baseline_dir = task_dir / "baseline"
        mcp_dir = task_dir / "mcp"
        
        for f in baseline_dir.rglob("trajectory.json"):
            baseline_traj = f
            break
        
        for f in mcp_dir.rglob("trajectory.json"):
            mcp_traj = f
            break
        
        # Find instruction
        benchmark_path = Path.cwd() / "benchmarks" / "big_code_mcp" / task_name / "instruction.md"
        
        if not baseline_traj or not mcp_traj or not benchmark_path.exists():
            print(f"⚠ {task_name}: Missing trajectories or instruction, skipping")
            continue
        
        print(f"Evaluating {task_name}...")
        try:
            result = judge_quality(task_name, baseline_traj, mcp_traj, benchmark_path)
            all_results.append(result)
            
            # Display results
            baseline_score = result["evaluation"].get("baseline", {}).get("overall", 0)
            mcp_score = result["evaluation"].get("mcp", {}).get("overall", 0)
            
            print(f"  Baseline: {baseline_score:.2f}/1.0")
            print(f"  MCP:      {mcp_score:.2f}/1.0")
            
            advantage = result["evaluation"].get("mcp_advantage", {})
            if advantage:
                print(f"  MCP advantage: {advantage.get('category')}")
            
            print()
        except Exception as e:
            print(f"  ERROR: {e}")
            print()
    
    # Summary
    print("=" * 120)
    print("EVALUATION SUMMARY")
    print("=" * 120)
    print()
    
    baseline_avg = sum(r["evaluation"].get("baseline", {}).get("overall", 0) for r in all_results) / len(all_results)
    mcp_avg = sum(r["evaluation"].get("mcp", {}).get("overall", 0) for r in all_results) / len(all_results)
    
    print(f"Average Baseline Score: {baseline_avg:.2f}/1.0")
    print(f"Average MCP Score:      {mcp_avg:.2f}/1.0")
    print(f"MCP Advantage:          {mcp_avg - baseline_avg:+.2f}")
    print()
    
    # Write detailed results
    output_file = Path("llm_judge_results.json")
    with open(output_file, "w") as f:
        json.dump(all_results, f, indent=2)
    
    print(f"Full results saved to: {output_file}")


if __name__ == "__main__":
    main()
