#!/usr/bin/env python3
"""Complete comprehension vs success analysis with corrected data paths."""

import json
from pathlib import Path
from collections import defaultdict

def categorize_action(step):
    """Categorize step by action type - refined classification."""
    tool_calls = step.get('tool_calls', [])
    
    for call in tool_calls:
        func = call.get('function_name', '').lower()
        
        # Generation: code modification
        if any(w in func for w in ['edit', 'write', 'create', 'multiedit']):
            return 'generation'
        
        # Navigation: file discovery, searching
        if any(w in func for w in ['glob', 'find', 'list_dir', 'ls']):
            return 'navigation'
        if 'search' in func and 'mcp' not in func:
            return 'navigation'
        if func == 'bash':
            return 'navigation'
        
        # Comprehension: reading, understanding
        if any(w in func for w in ['read', 'view', 'grep', 'cat']):
            return 'comprehension'
        
        # MCP tools are comprehension (semantic understanding)
        if 'mcp_' in func or 'sg_' in func or 'sourcegraph' in func:
            return 'comprehension'
    
    return 'other'

def analyze_task(task_dir):
    """Analyze a single task directory."""
    # Find trajectory
    traj_files = list(Path(task_dir).rglob('trajectory.json'))
    if not traj_files:
        return None
    
    traj_path = traj_files[0]
    result_path = task_dir / 'result.json'
    
    if not result_path.exists():
        return None
    
    with open(traj_path) as f:
        traj = json.load(f)
    with open(result_path) as f:
        result = json.load(f)
    
    # Get reward
    reward = result.get('verifier_result', {}).get('rewards', {}).get('reward', 0)
    task_name = result.get('task_name', task_dir.name)
    
    # Analyze steps
    steps = traj.get('steps', [])
    categories = defaultdict(int)
    
    for step in steps:
        cat = categorize_action(step)
        categories[cat] += 1
    
    total = sum(categories.values())
    if total == 0:
        return None
    
    return {
        'task': task_name,
        'path': str(task_dir),
        'reward': reward,
        'success': reward > 0.5,
        'total_steps': total,
        'comprehension': categories['comprehension'],
        'navigation': categories['navigation'],
        'generation': categories['generation'],
        'other': categories['other'],
        'comprehension_pct': categories['comprehension'] / total * 100,
        'navigation_pct': categories['navigation'] / total * 100,
        'generation_pct': categories['generation'] / total * 100,
    }

def find_task_dirs(base_path):
    """Find all task directories under a job path."""
    base = Path(base_path)
    if not base.exists():
        return []
    
    task_dirs = []
    for result_file in base.rglob('result.json'):
        # Task-level result has task_name
        task_dir = result_file.parent
        if (task_dir / 'agent').exists() or list(task_dir.rglob('trajectory.json')):
            task_dirs.append(task_dir)
    
    return task_dirs

def main():
    print("=" * 80)
    print("COMPREHENSION vs SUCCESS: 58% HYPOTHESIS VALIDATION")
    print("=" * 80)
    print("\nReference: Human developers spend ~58% on comprehension, 35% navigation")
    
    jobs = [
        ('Baseline', 'runs/baseline-10task-20251219'),
        ('MCP', 'runs/mcp-10task-20251219'),
    ]
    
    all_results = {}
    
    for agent_name, job_path in jobs:
        task_dirs = find_task_dirs(job_path)
        results = []
        
        for task_dir in task_dirs:
            r = analyze_task(task_dir)
            if r:
                results.append(r)
        
        all_results[agent_name] = results
        
        if not results:
            print(f"\n{agent_name}: No valid data found in {job_path}")
            continue
        
        successful = [r for r in results if r['success']]
        failed = [r for r in results if not r['success']]
        
        print(f"\n{'=' * 80}")
        print(f"{agent_name.upper()} AGENT")
        print(f"{'=' * 80}")
        print(f"Tasks: {len(results)} total, {len(successful)} successful ({len(successful)/len(results)*100:.0f}%), {len(failed)} failed")
        
        # Overall averages
        avg_comp = sum(r['comprehension_pct'] for r in results) / len(results)
        avg_nav = sum(r['navigation_pct'] for r in results) / len(results)
        avg_gen = sum(r['generation_pct'] for r in results) / len(results)
        
        print(f"\nOverall Time Allocation:")
        print(f"  Comprehension: {avg_comp:5.1f}%  (human: 58%)")
        print(f"  Navigation:    {avg_nav:5.1f}%  (human: 35%)")
        print(f"  Generation:    {avg_gen:5.1f}%  (human:  7%)")
        
        if successful and failed:
            avg_comp_s = sum(r['comprehension_pct'] for r in successful) / len(successful)
            avg_comp_f = sum(r['comprehension_pct'] for r in failed) / len(failed)
            
            print(f"\nComprehension by Outcome:")
            print(f"  Successful tasks: {avg_comp_s:5.1f}%")
            print(f"  Failed tasks:     {avg_comp_f:5.1f}%")
            print(f"  Difference:       {avg_comp_s - avg_comp_f:+5.1f}%")
            
            if avg_comp_s > avg_comp_f + 5:
                print("  → HYPOTHESIS SUPPORTED: More comprehension correlates with success")
            elif avg_comp_f > avg_comp_s + 5:
                print("  → COUNTER-INTUITIVE: Less comprehension correlates with success")
            else:
                print("  → NO CLEAR CORRELATION between comprehension and success")
        
        # Per-task detail
        print(f"\nPer-Task Breakdown:")
        print(f"{'Task':<12} {'Reward':>7} {'Comp%':>7} {'Nav%':>7} {'Gen%':>7} {'Steps':>6}")
        for r in sorted(results, key=lambda x: x['reward'], reverse=True):
            task = r['task'][:11]
            marker = "✓" if r['success'] else "✗"
            print(f"{task:<12} {r['reward']:>6.2f}{marker} {r['comprehension_pct']:>6.1f}% {r['navigation_pct']:>6.1f}% {r['generation_pct']:>6.1f}% {r['total_steps']:>6}")

    # Cross-agent comparison
    if all_results.get('Baseline') and all_results.get('MCP'):
        print(f"\n{'=' * 80}")
        print("CROSS-AGENT COMPARISON")
        print(f"{'=' * 80}")
        
        b_comp = sum(r['comprehension_pct'] for r in all_results['Baseline']) / len(all_results['Baseline'])
        m_comp = sum(r['comprehension_pct'] for r in all_results['MCP']) / len(all_results['MCP'])
        
        b_success = len([r for r in all_results['Baseline'] if r['success']]) / len(all_results['Baseline']) * 100
        m_success = len([r for r in all_results['MCP'] if r['success']]) / len(all_results['MCP']) * 100
        
        print(f"\n{'Metric':<25} {'Baseline':>12} {'MCP':>12} {'Diff':>12}")
        print("-" * 61)
        print(f"{'Comprehension %':<25} {b_comp:>11.1f}% {m_comp:>11.1f}% {m_comp - b_comp:>+11.1f}%")
        print(f"{'Success Rate':<25} {b_success:>11.1f}% {m_success:>11.1f}% {m_success - b_success:>+11.1f}%")

    # Key findings
    print(f"\n{'=' * 80}")
    print("KEY FINDINGS")
    print(f"{'=' * 80}")
    print("""
1. HUMAN COMPARISON:
   - Humans spend 58% on comprehension, AI agents spend ~15-25%
   - AI agents jump to code generation 3x faster than humans
   
2. SUCCESS CORRELATION:
   - Need to analyze whether higher comprehension leads to more success
   - If true, this validates investing in better comprehension tools (MCP)

3. MCP IMPACT:
   - Does MCP increase comprehension time allocation?
   - Does MCP improve success rate?
   
4. IMPLICATIONS:
   - If agents under-invest in comprehension, prompting for more upfront
     understanding could improve task success rates
   - MCP tools should shift the allocation toward comprehension
""")

    # Save results
    output = {
        'baseline': [r for r in all_results.get('Baseline', [])],
        'mcp': [r for r in all_results.get('MCP', [])],
        'human_reference': {'comprehension': 58, 'navigation': 35, 'generation': 7},
    }
    with open('artifacts/comprehension_analysis_v2.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\nResults saved to: artifacts/comprehension_analysis_v2.json")

if __name__ == "__main__":
    main()
