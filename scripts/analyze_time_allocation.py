#!/usr/bin/env python3
"""Analyze time allocation patterns: comprehension vs generation.

Tests hypothesis: Do AI agents mirror human time allocation (58% comprehension)?
"""

import json
from pathlib import Path
from collections import defaultdict

def categorize_action(step):
    """Categorize a step as comprehension, navigation, or generation."""
    message = step.get('message', '')
    tool_calls = step.get('tool_calls', [])
    
    # Check tool calls first
    for call in tool_calls:
        func = call.get('function_name', '').lower()
        
        # Generation actions (modifying code)
        if func in ['edit', 'write', 'multiedit', 'multiwrite']:
            return 'generation'
        
        # Navigation actions
        if func in ['glob', 'bash'] or 'search' in func:
            return 'navigation'
        
        # Comprehension actions  
        if func in ['read', 'grep'] or 'fetch' in func:
            return 'comprehension'
        
        # MCP tools are comprehension
        if 'mcp_' in func or 'sg_' in func:
            return 'comprehension'
    
    # If no tool calls, classify by message content
    if isinstance(message, str):
        msg_lower = message.lower()
        if any(w in msg_lower for w in ['edit', 'write', 'create', 'add', 'modify', 'fix']):
            return 'generation'
        if any(w in msg_lower for w in ['find', 'search', 'look', 'navigate']):
            return 'navigation'
        if any(w in msg_lower for w in ['read', 'understand', 'analyze', 'review']):
            return 'comprehension'
    
    return 'other'


def analyze_trajectory(traj_path):
    """Analyze a single trajectory file."""
    with open(traj_path) as f:
        data = json.load(f)
    
    steps = data.get('steps', [])
    
    categories = defaultdict(int)
    tokens_by_category = defaultdict(int)
    
    for step in steps:
        cat = categorize_action(step)
        categories[cat] += 1
        
        # Count tokens
        if 'metrics' in step:
            tokens = step['metrics'].get('prompt_tokens', 0) + step['metrics'].get('completion_tokens', 0)
            tokens_by_category[cat] += tokens
    
    total_steps = sum(categories.values())
    total_tokens = sum(tokens_by_category.values())
    
    return {
        'total_steps': total_steps,
        'total_tokens': total_tokens,
        'steps': dict(categories),
        'tokens': dict(tokens_by_category),
        'step_pct': {k: v/total_steps*100 if total_steps > 0 else 0 for k, v in categories.items()},
        'token_pct': {k: v/total_tokens*100 if total_tokens > 0 else 0 for k, v in tokens_by_category.items()},
    }


def analyze_all(base_path):
    """Analyze all trajectories in a directory."""
    results = []
    
    for traj_path in Path(base_path).rglob('trajectory.json'):
        try:
            result = analyze_trajectory(traj_path)
            result['path'] = str(traj_path)
            results.append(result)
        except Exception as e:
            print(f"Error: {traj_path}: {e}")
    
    return results


def aggregate(results):
    """Aggregate results across tasks."""
    if not results:
        return {}
    
    total_steps = defaultdict(int)
    total_tokens = defaultdict(int)
    
    for r in results:
        for cat, count in r['steps'].items():
            total_steps[cat] += count
        for cat, count in r['tokens'].items():
            total_tokens[cat] += count
    
    sum_steps = sum(total_steps.values())
    sum_tokens = sum(total_tokens.values())
    
    return {
        'total_steps': dict(total_steps),
        'total_tokens': dict(total_tokens),
        'step_pct': {k: v/sum_steps*100 if sum_steps > 0 else 0 for k, v in total_steps.items()},
        'token_pct': {k: v/sum_tokens*100 if sum_tokens > 0 else 0 for k, v in total_tokens.items()},
    }


def main():
    baseline_results = analyze_all('jobs/baseline-10task-20251219')
    mcp_results = analyze_all('jobs/mcp-10task-20251219')
    
    baseline_agg = aggregate(baseline_results)
    mcp_agg = aggregate(mcp_results)
    
    print("=" * 70)
    print("TIME ALLOCATION ANALYSIS: 58% COMPREHENSION HYPOTHESIS")
    print("=" * 70)
    print()
    print("Reference: Human developers spend ~58% on comprehension, 35% navigation, ~7% coding")
    print()
    
    print("-" * 70)
    print("BASELINE AGENT")
    print("-" * 70)
    print(f"{'Category':<20} {'Steps':>10} {'Step %':>10} {'Tokens':>15} {'Token %':>10}")
    for cat in ['comprehension', 'navigation', 'generation', 'other']:
        steps = baseline_agg['total_steps'].get(cat, 0)
        step_pct = baseline_agg['step_pct'].get(cat, 0)
        tokens = baseline_agg['total_tokens'].get(cat, 0)
        token_pct = baseline_agg['token_pct'].get(cat, 0)
        print(f"{cat:<20} {steps:>10,} {step_pct:>10.1f}% {tokens:>15,} {token_pct:>10.1f}%")
    
    print()
    print("-" * 70)
    print("MCP AGENT")
    print("-" * 70)
    print(f"{'Category':<20} {'Steps':>10} {'Step %':>10} {'Tokens':>15} {'Token %':>10}")
    for cat in ['comprehension', 'navigation', 'generation', 'other']:
        steps = mcp_agg['total_steps'].get(cat, 0)
        step_pct = mcp_agg['step_pct'].get(cat, 0)
        tokens = mcp_agg['total_tokens'].get(cat, 0)
        token_pct = mcp_agg['token_pct'].get(cat, 0)
        print(f"{cat:<20} {steps:>10,} {step_pct:>10.1f}% {tokens:>15,} {token_pct:>10.1f}%")
    
    print()
    print("=" * 70)
    print("HYPOTHESIS VALIDATION")
    print("=" * 70)
    
    baseline_comp = baseline_agg['step_pct'].get('comprehension', 0)
    mcp_comp = mcp_agg['step_pct'].get('comprehension', 0)
    
    print(f"""
Human reference:     58% comprehension
Baseline agent:      {baseline_comp:.1f}% comprehension
MCP agent:           {mcp_comp:.1f}% comprehension

Baseline vs Human:   {baseline_comp - 58:+.1f}% difference
MCP vs Human:        {mcp_comp - 58:+.1f}% difference
MCP vs Baseline:     {mcp_comp - baseline_comp:+.1f}% difference
""")

    if mcp_comp > baseline_comp:
        print("FINDING: MCP agent shows HIGHER comprehension ratio (+{:.1f}%)".format(mcp_comp - baseline_comp))
        print("         This aligns with expectation: MCP encourages more upfront understanding")
    else:
        print("FINDING: MCP agent shows LOWER comprehension ratio ({:.1f}%)".format(mcp_comp - baseline_comp))
        print("         Counter to expectation: MCP should encourage more comprehension")
    
    # Save results
    output = {
        'baseline': {'tasks': len(baseline_results), 'aggregate': baseline_agg},
        'mcp': {'tasks': len(mcp_results), 'aggregate': mcp_agg},
        'human_reference': {'comprehension': 58, 'navigation': 35, 'generation': 7},
    }
    
    with open('artifacts/time_allocation_analysis.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\nResults saved to: artifacts/time_allocation_analysis.json")


if __name__ == "__main__":
    main()
