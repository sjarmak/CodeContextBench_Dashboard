#!/usr/bin/env python3
"""
Aggregate and analyze MCP comparison experiment results.

Processes harbor execution results and generates:
- Success rates by agent
- Duration analysis
- Tool usage patterns
- Comparative statistics
"""

import json
import sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime

def load_experiment_results(results_dir):
    """Load all results from an experiment directory."""
    results_dir = Path(results_dir)
    if not results_dir.exists():
        print(f"Results directory not found: {results_dir}")
        return None
    
    # Load summary
    summary_file = results_dir / "summary.json"
    if not summary_file.exists():
        print(f"Summary file not found: {summary_file}")
        return None
    
    with open(summary_file) as f:
        summary = json.load(f)
    
    print(f"\n{'='*60}")
    print("MCP Comparison Experiment Results")
    print(f"{'='*60}")
    print(f"Experiment: {summary.get('experiment')}")
    print(f"Timestamp: {summary.get('timestamp')}")
    print(f"Benchmark: {summary.get('benchmark')}")
    print(f"Model: {summary.get('model')}")
    
    # Load individual agent results
    agents_results = {}
    for agent_result in summary.get('agents', []):
        agent_name = agent_result['name']
        agent_file = results_dir / f"{agent_name}.json"
        
        if agent_file.exists():
            with open(agent_file) as f:
                agent_data = json.load(f)
            agents_results[agent_name] = agent_data
            
            # Print agent status
            status = "✓ PASS" if agent_data.get('success') else "✗ FAIL"
            print(f"  {agent_data['display']:<30} {status}")
        else:
            agents_results[agent_name] = agent_result
            status = "✓ PASS" if agent_result.get('success') else "✗ FAIL"
            print(f"  {agent_result['display']:<30} {status}")
    
    return {
        "summary": summary,
        "agents": agents_results,
        "results_dir": results_dir
    }

def calculate_statistics(experiment_data):
    """Calculate summary statistics."""
    agents = experiment_data['agents']
    summary = experiment_data['summary']
    
    successes = sum(1 for a in agents.values() if a.get('success'))
    total = len(agents)
    success_rate = (successes / total * 100) if total > 0 else 0
    
    stats = {
        "total_agents": total,
        "successful": successes,
        "failed": total - successes,
        "success_rate": success_rate,
        "timestamp": datetime.now().isoformat()
    }
    
    print(f"\nStatistics:")
    print(f"  Total agents: {stats['total_agents']}")
    print(f"  Successful: {stats['successful']}")
    print(f"  Failed: {stats['failed']}")
    print(f"  Success rate: {stats['success_rate']:.1f}%")
    
    return stats

def compare_agents(experiment_data):
    """Generate agent comparison matrix."""
    print(f"\nAgent Comparison:")
    print(f"{'Agent':<30} {'Status':<10} {'Return Code':<12}")
    print(f"{'-'*52}")
    
    for agent_data in experiment_data['summary']['agents']:
        agent_name = agent_data['display']
        agent_key = agent_data['name']
        
        result = experiment_data['agents'].get(agent_key, {})
        status = "PASS" if result.get('success') else "FAIL"
        returncode = result.get('returncode', 'N/A')
        
        print(f"{agent_name:<30} {status:<10} {str(returncode):<12}")

def generate_report(experiment_data):
    """Generate comprehensive analysis report."""
    report = {
        "experiment": "swebench_mcp_comparison",
        "generated_at": datetime.now().isoformat(),
        "summary": experiment_data['summary'],
        "statistics": calculate_statistics(experiment_data),
    }
    
    return report

def save_report(report, results_dir):
    """Save analysis report."""
    report_file = Path(results_dir) / "analysis_report.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\nReport saved: {report_file}")
    return report_file

def main():
    if len(sys.argv) < 2:
        # Find most recent experiment
        results_base = Path("results")
        experiments = sorted(
            [d for d in results_base.iterdir() if d.is_dir() and d.name.startswith("swebench_comparison")],
            key=lambda x: x.name,
            reverse=True
        )
        
        if not experiments:
            print("No experiment results found")
            return 1
        
        results_dir = experiments[0]
    else:
        results_dir = sys.argv[1]
    
    # Load results
    experiment_data = load_experiment_results(results_dir)
    if not experiment_data:
        return 1
    
    # Generate analysis
    report = generate_report(experiment_data)
    compare_agents(experiment_data)
    
    # Save report
    save_report(report, results_dir)
    
    print(f"\n{'='*60}")
    print("Analysis Complete")
    print(f"{'='*60}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
