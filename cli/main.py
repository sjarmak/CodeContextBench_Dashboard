#!/usr/bin/env python3
"""
CodeContextBench CLI - Observability platform for Harbor evaluations.

Usage:
    ccb sync push [--dry-run]
    ccb sync pull [--experiment=ID] [--dry-run]
    ccb translate <agent_id> [--output-dir=DIR]
    ccb experiment list
    ccb experiment status <experiment_id>
    ccb config validate
    ccb ingest [<experiment_id>] [-v|--verbose]
"""

import argparse
import sys
from pathlib import Path


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent


def cmd_sync_push(args):
    """Push configs to VM."""
    from src.sync import push_configs, SyncManifest
    from src.config.loader import ConfigLoader
    from src.translate import ClaudeCodeTranslator, OpenCodeTranslator, OpenHandsTranslator
    
    project_root = get_project_root()
    config_dir = project_root / "configs"
    output_dir = project_root / "data" / "translated_configs"
    
    # Load and translate all agent configs
    loader = ConfigLoader(config_dir)
    agents = loader.list_agents()
    
    translators = {
        "claudecode": ClaudeCodeTranslator(),
        "opencode": OpenCodeTranslator(),
        "openhands": OpenHandsTranslator(),
    }
    
    print(f"Translating {len(agents)} agent configs...")
    for agent_id in agents:
        if agent_id.startswith("_"):
            continue
        
        agent_config = loader.load_agent(agent_id)
        
        # Load MCP endpoints
        mcp_endpoints = []
        for endpoint_id in agent_config.mcp_endpoints:
            mcp_endpoints.append(loader.load_mcp_endpoint(endpoint_id))
        
        # Translate for each agent type
        for agent_type, translator in translators.items():
            agent_output = output_dir / agent_type / agent_id
            translator.translate(agent_config, mcp_endpoints, agent_output)
            print(f"  Translated {agent_id} for {agent_type}")
    
    # Push to VM
    if not args.dry_run:
        manifest = SyncManifest.load(project_root / "data" / "sync_manifest.json")
        
        if not manifest.vm_host:
            print("Error: VM host not configured. Set vm_host in sync_manifest.json")
            return 1
        
        result = push_configs(
            output_dir,
            manifest.vm_host,
            manifest.vm_path or "~/evals/configs",
            manifest,
            dry_run=args.dry_run,
        )
        
        if result.success:
            print(f"Pushed {result.files_synced} files to VM")
            manifest.save(project_root / "data" / "sync_manifest.json")
        else:
            print(f"Push failed: {result.error}")
            return 1
    else:
        print("Dry run - configs translated but not pushed")
    
    return 0


def cmd_sync_pull(args):
    """Pull results from VM."""
    from src.sync import pull_results, SyncManifest
    
    project_root = get_project_root()
    manifest = SyncManifest.load(project_root / "data" / "sync_manifest.json")
    
    if not manifest.vm_host:
        print("Error: VM host not configured. Set vm_host in sync_manifest.json")
        return 1
    
    result = pull_results(
        manifest.vm_host,
        manifest.vm_path + "/jobs" if manifest.vm_path else "~/evals/jobs",
        project_root / "data" / "results",
        experiment_id=args.experiment,
        manifest=manifest,
        dry_run=args.dry_run,
    )
    
    if result.success:
        print(f"Pulled {result.files_synced} files")
        print(f"Experiments found: {', '.join(result.experiments_found)}")
        if not args.dry_run:
            manifest.save(project_root / "data" / "sync_manifest.json")
    else:
        print(f"Pull failed: {result.error}")
        return 1
    
    return 0


def cmd_translate(args):
    """Translate an agent config to all agent-specific formats."""
    from src.config.loader import ConfigLoader
    from src.translate import ClaudeCodeTranslator, OpenCodeTranslator, OpenHandsTranslator
    
    project_root = get_project_root()
    config_dir = project_root / "configs"
    output_dir = Path(args.output_dir) if args.output_dir else project_root / "data" / "translated_configs"
    
    loader = ConfigLoader(config_dir)
    
    try:
        agent_config = loader.load_agent(args.agent_id)
    except FileNotFoundError:
        print(f"Agent config not found: {args.agent_id}")
        return 1
    
    # Load MCP endpoints
    mcp_endpoints = []
    for endpoint_id in agent_config.mcp_endpoints:
        mcp_endpoints.append(loader.load_mcp_endpoint(endpoint_id))
    
    translators = {
        "claudecode": ClaudeCodeTranslator(),
        "opencode": OpenCodeTranslator(),
        "openhands": OpenHandsTranslator(),
    }
    
    for agent_type, translator in translators.items():
        agent_output = output_dir / agent_type / args.agent_id
        files = translator.translate(agent_config, mcp_endpoints, agent_output)
        print(f"{agent_type}:")
        for file_type, path in files.items():
            print(f"  {file_type}: {path}")
    
    return 0


def cmd_experiment_list(args):
    """List all experiments."""
    from src.config.loader import ConfigLoader
    
    project_root = get_project_root()
    loader = ConfigLoader(project_root / "configs")
    
    experiments = loader.list_experiments()
    
    if not experiments:
        print("No experiments found in configs/experiments/")
        return 0
    
    print(f"Found {len(experiments)} experiments:\n")
    for exp_id in experiments:
        try:
            exp = loader.load_experiment(exp_id)
            print(f"  {exp_id}")
            print(f"    Name: {exp.name}")
            print(f"    Status: {exp.status}")
            print(f"    Agents: {', '.join(exp.agents)}")
            print()
        except Exception as e:
            print(f"  {exp_id} (error: {e})")
    
    return 0


def cmd_config_validate(args):
    """Validate all configurations."""
    from src.config.loader import ConfigLoader
    
    project_root = get_project_root()
    loader = ConfigLoader(project_root / "configs")
    
    errors = []
    
    # Validate agents
    print("Validating agents...")
    for agent_id in loader.list_agents():
        try:
            loader.load_agent(agent_id)
            print(f"  ✓ {agent_id}")
        except Exception as e:
            print(f"  ✗ {agent_id}: {e}")
            errors.append(f"Agent {agent_id}: {e}")
    
    # Validate experiments
    print("\nValidating experiments...")
    for exp_id in loader.list_experiments():
        try:
            loader.load_experiment(exp_id)
            print(f"  ✓ {exp_id}")
        except Exception as e:
            print(f"  ✗ {exp_id}: {e}")
            errors.append(f"Experiment {exp_id}: {e}")
    
    if errors:
        print(f"\n{len(errors)} validation errors found")
        return 1
    else:
        print("\nAll configs valid ✓")
        return 0


def cmd_ingest(args):
    """Ingest experiment results."""
    from src.ingest import HarborResultParser, TranscriptParser, MetricsDatabase
    from pathlib import Path
    
    project_root = get_project_root()
    results_dir = project_root / "data" / "results"
    db_path = project_root / "data" / "metrics.db"
    
    if not results_dir.exists():
        print(f"Error: Results directory not found: {results_dir}")
        return 1
    
    # Find experiment directories
    experiment_id = args.experiment
    
    if experiment_id:
        exp_dir = results_dir / experiment_id
        if not exp_dir.exists():
            print(f"Error: Experiment not found: {experiment_id}")
            return 1
        experiments = [exp_dir]
    else:
        # Ingest all experiments
        experiments = [d for d in results_dir.iterdir() if d.is_dir()]
    
    if not experiments:
        print(f"No experiments found in {results_dir}")
        return 0
    
    # Initialize database
    db = MetricsDatabase(db_path)
    parser = HarborResultParser()
    transcript_parser = TranscriptParser()
    
    total_tasks = 0
    successful = 0
    
    for exp_path in experiments:
        exp_id = exp_path.name
        print(f"\nIngesting experiment: {exp_id}")
        
        # Find job directories
        for job_dir in exp_path.iterdir():
            if not job_dir.is_dir() or job_dir.name.startswith("."):
                continue
            
            job_id = job_dir.name
            result_file = job_dir / "result.json"
            transcript_file = job_dir / "claude-code.txt"
            
            if not result_file.exists():
                print(f"  ⚠ {job_id}: result.json not found")
                continue
            
            total_tasks += 1
            
            try:
                # Parse Harbor result
                harbor_result = parser.parse_file(result_file)
                db.store_harbor_result(harbor_result, exp_id, job_id)
                
                # Parse transcript if available
                if transcript_file.exists():
                    transcript_metrics = transcript_parser.parse_file(transcript_file)
                    db.store_tool_usage(harbor_result.task_id, transcript_metrics, exp_id, job_id)
                
                status = "✓" if harbor_result.passed else "✗"
                print(f"  {status} {job_id}")
                successful += 1
                
            except Exception as e:
                print(f"  ✗ {job_id}: {e}")
                if args.verbose:
                    import traceback
                    traceback.print_exc()
        
        # Update experiment summary
        db.update_experiment_summary(exp_id)
    
    print(f"\n✓ Ingested {successful}/{total_tasks} tasks")
    
    # Print stats
    if successful > 0:
        print(f"\nDatabase: {db_path}")
        stats = db.get_stats()
        print(f"\nOverall Stats:")
        print(f"  Pass rate: {stats['harbor']['pass_rate']:.1%}")
        print(f"  Avg duration: {stats['harbor']['avg_duration_seconds']:.1f}s")
        print(f"\nTool Usage:")
        print(f"  Avg MCP calls: {stats['tool_usage']['avg_mcp_calls']:.1f}")
        print(f"  Avg Deep Search calls: {stats['tool_usage']['avg_deep_search_calls']:.1f}")
        print(f"  Avg Local calls: {stats['tool_usage']['avg_local_calls']:.1f}")
    
    return 0 if successful > 0 else 1


def cmd_analyze(args):
    """Dispatch to analysis subcommands."""
    from cli.analyze_cmd import (
        cmd_analyze_compare,
        cmd_analyze_failures,
        cmd_analyze_ir,
        cmd_analyze_recommend,
    )
    
    if args.analyze_command == "compare":
        return cmd_analyze_compare(args)
    elif args.analyze_command == "failures":
        return cmd_analyze_failures(args)
    elif args.analyze_command == "ir":
        return cmd_analyze_ir(args)
    elif args.analyze_command == "recommend":
        return cmd_analyze_recommend(args)
    else:
        print("Unknown analyze command")
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="CodeContextBench CLI - Observability platform for Harbor evaluations"
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # sync command
    sync_parser = subparsers.add_parser("sync", help="Sync with VM")
    sync_subparsers = sync_parser.add_subparsers(dest="sync_command")
    
    push_parser = sync_subparsers.add_parser("push", help="Push configs to VM")
    push_parser.add_argument("--dry-run", action="store_true", help="Show what would be synced")
    
    pull_parser = sync_subparsers.add_parser("pull", help="Pull results from VM")
    pull_parser.add_argument("--experiment", help="Specific experiment ID to pull")
    pull_parser.add_argument("--dry-run", action="store_true", help="Show what would be synced")
    
    # translate command
    translate_parser = subparsers.add_parser("translate", help="Translate agent config")
    translate_parser.add_argument("agent_id", help="Agent ID to translate")
    translate_parser.add_argument("--output-dir", help="Output directory")
    
    # experiment command
    exp_parser = subparsers.add_parser("experiment", help="Manage experiments")
    exp_subparsers = exp_parser.add_subparsers(dest="exp_command")
    
    exp_subparsers.add_parser("list", help="List all experiments")
    
    status_parser = exp_subparsers.add_parser("status", help="Show experiment status")
    status_parser.add_argument("experiment_id", help="Experiment ID")
    
    # config command
    config_parser = subparsers.add_parser("config", help="Config management")
    config_subparsers = config_parser.add_subparsers(dest="config_command")
    
    config_subparsers.add_parser("validate", help="Validate all configs")
    
    # ingest command
    ingest_parser = subparsers.add_parser("ingest", help="Ingest evaluation results")
    ingest_parser.add_argument(
        "experiment",
        nargs="?",
        help="Specific experiment ID to ingest (ingests all if not specified)"
    )
    ingest_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show detailed error messages"
    )
    
    # analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze evaluation results")
    analyze_subparsers = analyze_parser.add_subparsers(dest="analyze_command")
    
    compare_parser = analyze_subparsers.add_parser("compare", help="Compare agents")
    compare_parser.add_argument("experiment_id", help="Experiment ID")
    compare_parser.add_argument("--baseline", help="Baseline agent (optional)")
    compare_parser.add_argument("-v", "--verbose", action="store_true")
    
    failures_parser = analyze_subparsers.add_parser("failures", help="Analyze failures")
    failures_parser.add_argument("experiment_id", help="Experiment ID")
    failures_parser.add_argument("--agent", help="Specific agent to analyze")
    failures_parser.add_argument("-v", "--verbose", action="store_true")
    
    ir_parser = analyze_subparsers.add_parser("ir", help="Analyze IR metrics")
    ir_parser.add_argument("experiment_id", help="Experiment ID")
    ir_parser.add_argument("--baseline", help="Baseline agent (optional)")
    ir_parser.add_argument("-v", "--verbose", action="store_true")
    
    rec_parser = analyze_subparsers.add_parser("recommend", help="Generate recommendations")
    rec_parser.add_argument("experiment_id", help="Experiment ID")
    rec_parser.add_argument("--agent", required=True, help="Agent to analyze")
    rec_parser.add_argument("-v", "--verbose", action="store_true")
    
    args = parser.parse_args()
    
    if args.command == "sync":
        if args.sync_command == "push":
            return cmd_sync_push(args)
        elif args.sync_command == "pull":
            return cmd_sync_pull(args)
    elif args.command == "translate":
        return cmd_translate(args)
    elif args.command == "experiment":
        if args.exp_command == "list":
            return cmd_experiment_list(args)
    elif args.command == "config":
        if args.config_command == "validate":
            return cmd_config_validate(args)
    elif args.command == "ingest":
        return cmd_ingest(args)
    elif args.command == "analyze":
        return cmd_analyze(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
