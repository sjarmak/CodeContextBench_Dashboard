#!/usr/bin/env python3
"""Update all task.toml files to include MCP setup and proper verification commands.

Applies the Harbor+MCP integration pattern to all tasks in benchmarks/.
"""

import re
from pathlib import Path

# Template for MCP setup scripts in [environment.setup_scripts]
MCP_SETUP_TEMPLATE = '''mcp_config = """#!/bin/bash
# Setup Sourcegraph MCP if credentials provided
if [ -n "$SOURCEGRAPH_ACCESS_TOKEN" ] && [ -n "$SOURCEGRAPH_URL" ]; then
  echo "Setting up Sourcegraph MCP configuration..."
  mkdir -p /root/.config/claude
  
  cat > /root/.config/claude/mcp.json << 'EOF'
{
  "mcpServers": {
    "sourcegraph": {
      "command": "npx",
      "args": ["-y", "@sourcegraph/mcp-server"],
      "env": {
        "SRC_ACCESS_TOKEN": "$SOURCEGRAPH_ACCESS_TOKEN",
        "SOURCEGRAPH_URL": "$SOURCEGRAPH_URL"
      }
    }
  }
}
EOF
  
  echo "✓ MCP configuration created"
else
  echo "No Sourcegraph credentials provided, MCP disabled"
fi
exit 0
"""'''

ENVIRONMENT_SECTION = f'''[environment]
build_timeout_sec = 1800.0

[environment.setup_scripts]
{MCP_SETUP_TEMPLATE}'''


def update_task_toml(task_path: Path) -> bool:
    """Update a single task.toml file.
    
    Returns True if updated, False if no changes needed.
    """
    content = task_path.read_text()
    
    # Check if already has environment section
    if '[environment]' in content:
        print(f"  ⚠ {task_path}: Already has [environment] section, skipping")
        return False
    
    # Update verification command from "make test" to proper test.sh
    content = re.sub(
        r'command = "make test"',
        'command = "bash /workspace/tests/test.sh"',
        content
    )
    
    # Add environment section at the end
    if not content.endswith('\n'):
        content += '\n'
    content += '\n' + ENVIRONMENT_SECTION + '\n'
    
    task_path.write_text(content)
    return True


def main():
    """Update all task.toml files in benchmarks/."""
    project_root = Path(__file__).parent.parent
    benchmark_dir = project_root / "benchmarks"
    
    if not benchmark_dir.exists():
        print(f"❌ Benchmark dir not found: {benchmark_dir}")
        return 1
    
    # Find all task.toml files
    task_files = list(benchmark_dir.rglob("task.toml"))
    print(f"Found {len(task_files)} task.toml files")
    
    updated = 0
    skipped = 0
    
    for task_file in sorted(task_files):
        try:
            if update_task_toml(task_file):
                print(f"  ✓ Updated: {task_file.relative_to(project_root)}")
                updated += 1
            else:
                skipped += 1
        except Exception as e:
            print(f"  ❌ Error updating {task_file}: {e}")
    
    print(f"\nResults: {updated} updated, {skipped} skipped")
    return 0


if __name__ == "__main__":
    exit(main())
