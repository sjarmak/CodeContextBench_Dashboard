#!/usr/bin/env python3
"""
Validate comparison results before analysis.

Checks for:
- API key authentication failures
- Missing tasks
- Zero token counts (indicates no actual execution)
- Incomplete trajectory files
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple


def check_directory(base_dir: Path, agent_type: str) -> Tuple[int, List[str]]:
    """Check a directory for API key failures and other issues."""
    
    issues = []
    task_count = 0
    
    trajectories = list(base_dir.rglob("trajectory.json"))
    
    if not trajectories:
        issues.append(f"❌ No trajectory files found in {base_dir}")
        return 0, issues
    
    tasks_by_name = {}
    
    for traj_file in trajectories:
        parts = traj_file.parts
        for part in parts:
            if part.startswith("sgt-"):
                task_name = part.split("__")[0]
                break
        
        try:
            with open(traj_file) as f:
                data = json.load(f)
        except Exception as e:
            issues.append(f"❌ {task_name}: Cannot read trajectory.json: {e}")
            continue
        
        task_count += 1
        steps = data.get('steps', [])
        final_metrics = data.get('final_metrics', {})
        tokens = final_metrics.get('total_prompt_tokens', 0)
        
        # Check for API key errors
        has_api_error = any("Invalid API key" in step.get('message', '') for step in steps)
        
        if has_api_error:
            issues.append(f"❌ {task_name}: API key authentication failure (Invalid API key error in trajectory)")
        
        # Check for zero tokens (indicates no execution)
        if tokens == 0 and len(steps) > 3:
            # More than 3 steps but no tokens = likely API failure
            issues.append(f"⚠️  {task_name}: Zero tokens ({len(steps)} steps) - may indicate API failure")
        
        tasks_by_name[task_name] = {
            'steps': len(steps),
            'tokens': tokens,
            'has_error': has_api_error,
        }
    
    # Check for missing tasks
    expected_tasks = [f"sgt-{i:03d}" for i in range(1, 11)]
    for expected in expected_tasks:
        if expected not in tasks_by_name:
            issues.append(f"❌ {expected}: Task not found")
    
    return task_count, issues


def main():
    """Validate comparison results in current directory."""
    
    if len(sys.argv) < 2:
        print("Usage: validate_comparison_results.py <baseline_dir> <mcp_dir>")
        print()
        print("Example:")
        print("  python scripts/validate_comparison_results.py \\")
        print("    jobs/comparison-20251219-1530/baseline \\")
        print("    jobs/comparison-20251219-1530/mcp")
        sys.exit(1)
    
    baseline_dir = Path(sys.argv[1])
    mcp_dir = Path(sys.argv[2])
    
    if not baseline_dir.exists():
        print(f"❌ Baseline directory not found: {baseline_dir}")
        sys.exit(1)
    
    if not mcp_dir.exists():
        print(f"❌ MCP directory not found: {mcp_dir}")
        sys.exit(1)
    
    print("=" * 100)
    print("VALIDATING COMPARISON RESULTS")
    print("=" * 100)
    print()
    
    # Check baseline
    print("BASELINE VALIDATION")
    print("-" * 100)
    b_count, b_issues = check_directory(baseline_dir, "baseline")
    
    if b_issues:
        for issue in b_issues:
            print(issue)
    else:
        print(f"✓ Baseline: {b_count}/10 tasks, no issues detected")
    print()
    
    # Check MCP
    print("MCP VALIDATION")
    print("-" * 100)
    m_count, m_issues = check_directory(mcp_dir, "mcp")
    
    if m_issues:
        for issue in m_issues:
            print(issue)
    else:
        print(f"✓ MCP: {m_count}/10 tasks, no issues detected")
    print()
    
    # Summary
    print("=" * 100)
    print("VALIDATION SUMMARY")
    print("=" * 100)
    
    total_issues = len(b_issues) + len(m_issues)
    
    if total_issues == 0:
        print("✅ ALL CHECKS PASSED - Results are valid for analysis")
        sys.exit(0)
    else:
        print(f"❌ {total_issues} ISSUES FOUND - Results may be invalid")
        print()
        print("RECOMMENDATION: Do NOT use these results until issues are fixed")
        sys.exit(1)


if __name__ == "__main__":
    main()
