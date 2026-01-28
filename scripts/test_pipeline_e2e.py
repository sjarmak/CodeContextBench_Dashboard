#!/usr/bin/env python3
"""
Test script for end-to-end pipeline with real SWEBench evaluation data.

This script:
1. Parses the result.json files from VM evaluation runs
2. Parses the claude-code.txt transcripts  
3. Extracts metrics and tool usage patterns
4. Compares MCP-enabled vs baseline runs
"""

import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ingest.swebench_parser import SWEBenchParser, SWEBenchResult
from ingest.transcript_parser import TranscriptParser


def parse_jsonl_transcript(transcript_path: Path) -> dict:
    """Parse JSONL transcript and extract tool usage metrics."""
    metrics = {
        "total_messages": 0,
        "assistant_messages": 0,
        "user_messages": 0,
        "tool_calls": {},
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "total_cache_creation_tokens": 0,
        "total_cache_read_tokens": 0,
        "model": None,
        "files_read": set(),
        "bash_commands": [],
    }
    
    with open(transcript_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            
            metrics["total_messages"] += 1
            msg_type = record.get("type")
            
            if msg_type == "assistant":
                metrics["assistant_messages"] += 1
                message = record.get("message", {})
                
                # Extract model info
                if not metrics["model"]:
                    metrics["model"] = message.get("model")
                
                # Extract token usage
                usage = message.get("usage", {})
                metrics["total_input_tokens"] += usage.get("input_tokens", 0)
                metrics["total_output_tokens"] += usage.get("output_tokens", 0)
                
                # Extract cache tokens
                cache_creation = usage.get("cache_creation", {})
                if cache_creation:
                    metrics["total_cache_creation_tokens"] += cache_creation.get("ephemeral_5m_input_tokens", 0)
                metrics["total_cache_read_tokens"] += usage.get("cache_read_input_tokens", 0)
                
                # Extract tool calls from content
                content = message.get("content", [])
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "tool_use":
                        tool_name = item.get("name", "unknown")
                        metrics["tool_calls"][tool_name] = metrics["tool_calls"].get(tool_name, 0) + 1
                        
                        # Track specific tool data
                        tool_input = item.get("input", {})
                        if tool_name == "Read":
                            file_path = tool_input.get("file_path", "")
                            if file_path:
                                metrics["files_read"].add(file_path)
                        elif tool_name == "Bash":
                            command = tool_input.get("command", "")
                            if command:
                                metrics["bash_commands"].append(command[:100])
            
            elif msg_type == "user":
                metrics["user_messages"] += 1
    
    # Convert set to list for JSON serialization
    metrics["files_read"] = list(metrics["files_read"])
    return metrics


def analyze_run(instance_dir: Path) -> dict:
    """Analyze a single evaluation run."""
    print(f"\n{'='*60}")
    print(f"Analyzing: {instance_dir.name}")
    print(f"{'='*60}")
    
    result = {
        "instance_dir": str(instance_dir),
        "instance_name": instance_dir.name,
    }
    
    # Parse result.json with SWEBench parser
    parser = SWEBenchParser()
    try:
        swebench_result = parser.parse_instance_dir(instance_dir)
        result["swebench_result"] = {
            "task_id": swebench_result.harbor_result.task_id,
            "passed": swebench_result.harbor_result.passed,
            "reward": swebench_result.harbor_result.verifier_result.reward,
            "duration_seconds": swebench_result.harbor_result.duration_seconds,
            "model_name": swebench_result.harbor_result.model_name,
            "agent_name": swebench_result.harbor_result.agent_name,
            "mcp_enabled": swebench_result.mcp_enabled,
            "mcp_servers": list(swebench_result.mcp_servers.keys()),
            "agent_execution_duration": swebench_result.agent_execution_duration,
            "verifier_duration": swebench_result.verifier_duration,
            "agent_import_path": swebench_result.agent_import_path,
        }
        print(f"  Task ID: {swebench_result.harbor_result.task_id}")
        print(f"  Passed: {swebench_result.harbor_result.passed}")
        print(f"  Reward: {swebench_result.harbor_result.verifier_result.reward}")
        print(f"  Model: {swebench_result.harbor_result.model_name}")
        print(f"  MCP Enabled: {swebench_result.mcp_enabled}")
        if swebench_result.mcp_servers:
            print(f"  MCP Servers: {list(swebench_result.mcp_servers.keys())}")
        print(f"  Agent Execution: {swebench_result.agent_execution_duration:.1f}s")
    except Exception as e:
        print(f"  ERROR parsing result.json: {e}")
        result["parse_error"] = str(e)
    
    # Parse transcript
    transcript_path = instance_dir / "agent" / "claude-code.txt"
    if transcript_path.exists():
        print(f"\n  Transcript Analysis:")
        try:
            transcript_metrics = parse_jsonl_transcript(transcript_path)
            result["transcript_metrics"] = transcript_metrics
            
            print(f"    Model: {transcript_metrics['model']}")
            print(f"    Messages: {transcript_metrics['total_messages']} ({transcript_metrics['assistant_messages']} assistant, {transcript_metrics['user_messages']} user)")
            print(f"    Input Tokens: {transcript_metrics['total_input_tokens']:,}")
            print(f"    Output Tokens: {transcript_metrics['total_output_tokens']:,}")
            print(f"    Cache Read: {transcript_metrics['total_cache_read_tokens']:,}")
            print(f"    Files Read: {len(transcript_metrics['files_read'])}")
            
            print(f"\n    Tool Usage:")
            for tool, count in sorted(transcript_metrics["tool_calls"].items(), key=lambda x: -x[1]):
                print(f"      {tool}: {count}")
        except Exception as e:
            print(f"    ERROR parsing transcript: {e}")
            result["transcript_error"] = str(e)
    else:
        print(f"\n  No transcript found at {transcript_path}")
    
    return result


def main():
    """Main entry point."""
    # Look for evaluation data
    evals_base = Path.home() / "evals" / "custom_agents" / "agents" / "claudecode" / "runs"
    
    if not evals_base.exists():
        print(f"ERROR: Evaluations directory not found: {evals_base}")
        print("Please ensure the evaluation data is synced from the VM.")
        return 1
    
    print(f"Scanning for evaluations in: {evals_base}")
    
    results = {
        "runs": [],
        "summary": {
            "total_runs": 0,
            "mcp_runs": 0,
            "baseline_runs": 0,
            "passed_runs": 0,
            "failed_runs": 0,
        }
    }
    
    # Find all job directories
    for job_dir in evals_base.iterdir():
        if not job_dir.is_dir():
            continue
        if job_dir.name.startswith("."):
            continue
        
        print(f"\n\n{'#'*70}")
        print(f"JOB: {job_dir.name}")
        print(f"{'#'*70}")
        
        # Find instance directories within job
        for item in job_dir.iterdir():
            if not item.is_dir():
                continue
            if not item.name.startswith("instance_"):
                continue
            
            # Found an instance directory
            result = analyze_run(item)
            results["runs"].append(result)
            results["summary"]["total_runs"] += 1
            
            # Update summary
            if "swebench_result" in result:
                sr = result["swebench_result"]
                if sr.get("mcp_enabled"):
                    results["summary"]["mcp_runs"] += 1
                else:
                    results["summary"]["baseline_runs"] += 1
                
                if sr.get("passed"):
                    results["summary"]["passed_runs"] += 1
                else:
                    results["summary"]["failed_runs"] += 1
    
    # Print summary
    print(f"\n\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"Total Runs: {results['summary']['total_runs']}")
    print(f"MCP Runs: {results['summary']['mcp_runs']}")
    print(f"Baseline Runs: {results['summary']['baseline_runs']}")
    print(f"Passed: {results['summary']['passed_runs']}")
    print(f"Failed: {results['summary']['failed_runs']}")
    
    # Compare MCP vs Baseline
    if results["summary"]["mcp_runs"] > 0 and results["summary"]["baseline_runs"] > 0:
        print(f"\n{'='*70}")
        print("MCP vs BASELINE COMPARISON")
        print(f"{'='*70}")
        
        mcp_runs = [r for r in results["runs"] if r.get("swebench_result", {}).get("mcp_enabled")]
        baseline_runs = [r for r in results["runs"] if not r.get("swebench_result", {}).get("mcp_enabled")]
        
        def avg_duration(runs):
            durations = [r.get("swebench_result", {}).get("agent_execution_duration", 0) for r in runs]
            return sum(durations) / len(durations) if durations else 0
        
        def avg_tokens(runs, key):
            tokens = [r.get("transcript_metrics", {}).get(key, 0) for r in runs]
            return sum(tokens) / len(tokens) if tokens else 0
        
        def total_tool_calls(runs):
            total = {}
            for r in runs:
                for tool, count in r.get("transcript_metrics", {}).get("tool_calls", {}).items():
                    total[tool] = total.get(tool, 0) + count
            return total
        
        print(f"\nMCP Runs ({len(mcp_runs)}):")
        print(f"  Avg Execution Time: {avg_duration(mcp_runs):.1f}s")
        print(f"  Avg Input Tokens: {avg_tokens(mcp_runs, 'total_input_tokens'):,.0f}")
        print(f"  Avg Output Tokens: {avg_tokens(mcp_runs, 'total_output_tokens'):,.0f}")
        print(f"  Tool calls: {total_tool_calls(mcp_runs)}")
        
        print(f"\nBaseline Runs ({len(baseline_runs)}):")
        print(f"  Avg Execution Time: {avg_duration(baseline_runs):.1f}s")
        print(f"  Avg Input Tokens: {avg_tokens(baseline_runs, 'total_input_tokens'):,.0f}")
        print(f"  Avg Output Tokens: {avg_tokens(baseline_runs, 'total_output_tokens'):,.0f}")
        print(f"  Tool calls: {total_tool_calls(baseline_runs)}")
    
    # Save results to file
    output_path = Path(__file__).parent.parent / "jobs" / "pipeline_test_results.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Convert sets to lists for JSON serialization
    for run in results["runs"]:
        if "transcript_metrics" in run and "files_read" in run["transcript_metrics"]:
            run["transcript_metrics"]["files_read"] = list(run["transcript_metrics"]["files_read"])
    
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n\nResults saved to: {output_path}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
