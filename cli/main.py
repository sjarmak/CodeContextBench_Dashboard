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
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
