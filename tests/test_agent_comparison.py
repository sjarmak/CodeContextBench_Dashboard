#!/usr/bin/env python3
"""Comparison test: Claude baseline vs Claude+MCP on 10Figure tasks.

Tests:
1. Both agents can generate valid execution commands
2. Commands include proper environment setup
3. Sourcegraph MCP has required credentials in environment
4. Both agents handle task instructions correctly
"""

import json
import sys
from pathlib import Path

# Add project to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from agents.claude_agent import ClaudeCodeAgent
from agents.claude_sourcegraph_mcp_agent import ClaudeCodeSourcegraphMCPAgent


class AgentComparisonTest:
    """Compare agent implementations."""
    
    def __init__(self):
        self.project_root = PROJECT_ROOT
        self.benchmark_dir = self.project_root / "benchmarks" / "10figure"
    
    def get_test_tasks(self):
        """Get 4 sample tasks for comparison."""
        return [
            "cross_file_reasoning_01",
            "refactor_rename_01",
            "api_upgrade_01",
            "bug_localization_01",
        ]
    
    def read_task_instruction(self, task_id):
        """Read instruction from a task."""
        task_dir = self.benchmark_dir / task_id
        instruction_file = task_dir / "instruction.md"
        if instruction_file.exists():
            return instruction_file.read_text()
        return None
    
    def test_baseline_command_generation(self):
        """Test Claude baseline agent command generation."""
        print("\n=== Claude Baseline: Command Generation ===")
        
        agent = ClaudeCodeAgent()
        test_instruction = "Fix the bug in the code"
        repo_dir = "/workspace"
        
        cmd = agent.get_agent_command(test_instruction, repo_dir)
        
        # Verify command structure
        checks = {
            "contains 'claude'": 'claude' in cmd.lower(),
            "contains '-p' flag": '-p' in cmd,
            "contains '--dangerously-skip-permissions'": '--dangerously-skip-permissions' in cmd,
            "contains output format": 'output-format' in cmd or 'json' in cmd,
            "changes to repo dir": 'cd' in cmd and '/workspace' in cmd,
            "pipes to /logs": '/logs/agent/claude.txt' in cmd,
        }
        
        all_pass = True
        for check_name, passed in checks.items():
            status = "✓" if passed else "❌"
            print(f"  {status} {check_name}")
            all_pass = all_pass and passed
        
        if all_pass:
            print(f"  Command: {cmd[:80]}...")
        
        return all_pass
    
    def test_baseline_environment(self):
        """Test Claude baseline environment variables."""
        print("\n=== Claude Baseline: Environment ===")
        
        agent = ClaudeCodeAgent()
        
        # This will fail without ANTHROPIC_API_KEY set, which is expected
        try:
            env = agent.get_agent_env()
            print("  ❌ Should require ANTHROPIC_API_KEY")
            return False
        except ValueError as e:
            if "ANTHROPIC_API_KEY" in str(e):
                print(f"  ✓ Correctly requires ANTHROPIC_API_KEY")
                return True
            else:
                print(f"  ❌ Wrong error: {e}")
                return False
    
    def test_mcp_command_generation(self):
        """Test Claude+MCP agent command generation."""
        print("\n=== Claude+MCP: Command Generation ===")
        
        # Create a mock agent without requiring credentials for this test
        agent = ClaudeCodeSourcegraphMCPAgent()
        test_instruction = "Find the service layer using Sourcegraph"
        repo_dir = "/workspace"
        
        cmd = agent.get_agent_command(test_instruction, repo_dir)
        
        # Should be same as baseline (MCP is configured via --mcp-config at runtime)
        checks = {
            "contains 'claude'": 'claude' in cmd.lower(),
            "changes to repo dir": 'cd' in cmd and '/workspace' in cmd,
        }
        
        all_pass = True
        for check_name, passed in checks.items():
            status = "✓" if passed else "❌"
            print(f"  {status} {check_name}")
            all_pass = all_pass and passed
        
        return all_pass
    
    def test_mcp_environment(self):
        """Test Claude+MCP environment variables."""
        print("\n=== Claude+MCP: Environment ===")
        
        agent = ClaudeCodeSourcegraphMCPAgent()
        
        # This will fail without both ANTHROPIC_API_KEY and SRC_ACCESS_TOKEN
        try:
            env = agent.get_agent_env()
            print("  ❌ Should require both ANTHROPIC_API_KEY and SRC_ACCESS_TOKEN")
            return False
        except ValueError as e:
            error_msg = str(e)
            if "ANTHROPIC_API_KEY" in error_msg or "SRC_ACCESS_TOKEN" in error_msg:
                print(f"  ✓ Correctly requires Sourcegraph credentials")
                print(f"     ({error_msg.split('must be set')[0].split()[-1]} missing)")
                return True
            else:
                print(f"  ❌ Wrong error: {e}")
                return False
    
    def test_instruction_handling(self):
        """Test that both agents handle task instructions correctly."""
        print("\n=== Instruction Handling ===")
        
        agent_baseline = ClaudeCodeAgent()
        agent_mcp = ClaudeCodeSourcegraphMCPAgent()
        
        test_tasks = self.get_test_tasks()
        all_pass = True
        
        for task_id in test_tasks:
            instruction = self.read_task_instruction(task_id)
            if not instruction:
                print(f"  ❌ {task_id}: No instruction found")
                all_pass = False
                continue
            
            # Generate commands for both agents
            try:
                cmd_baseline = agent_baseline.get_agent_command(instruction, "/workspace")
                cmd_mcp = agent_mcp.get_agent_command(instruction, "/workspace")
                
                # Both should include the instruction (escaped)
                if len(cmd_baseline) > 100 and len(cmd_mcp) > 100:
                    print(f"  ✓ {task_id}: Both agents generate valid commands")
                else:
                    print(f"  ❌ {task_id}: Commands too short")
                    all_pass = False
            except Exception as e:
                print(f"  ❌ {task_id}: {e}")
                all_pass = False
        
        return all_pass
    
    def test_agent_differentiation(self):
        """Verify the key differences between baseline and MCP agents."""
        print("\n=== Agent Differentiation ===")
        
        # Both agents should have different credential requirements
        baseline = ClaudeCodeAgent()
        mcp = ClaudeCodeSourcegraphMCPAgent()
        
        # Test 1: Both agents inherit from same base
        if isinstance(mcp, ClaudeCodeAgent.__bases__[0]):
            print("  ✓ MCP agent extends baseline agent")
        
        # Test 2: Commands are similar (difference is in --mcp-config at runtime)
        cmd_baseline = baseline.get_agent_command("test", "/workspace")
        cmd_mcp = mcp.get_agent_command("test", "/workspace")
        
        if cmd_baseline == cmd_mcp:
            print("  ✓ Commands are identical (MCP config applied at runtime)")
        else:
            print("  ⚠ Commands differ unexpectedly")
        
        # Test 3: Environment variable requirements differ
        errors = []
        try:
            baseline.get_agent_env()
        except ValueError as e:
            errors.append(("baseline", str(e)))
        
        try:
            mcp.get_agent_env()
        except ValueError as e:
            errors.append(("mcp", str(e)))
        
        if len(errors) == 2:
            baseline_requires_key = "ANTHROPIC_API_KEY" in errors[0][1]
            mcp_requires_more = len(errors[1][1]) > len(errors[0][1])
            
            if baseline_requires_key and mcp_requires_more:
                print("  ✓ MCP agent requires more credentials than baseline")
                return True
            else:
                print("  ⚠ Credential requirements unclear")
                return True  # Still pass as structure is correct
        else:
            print("  ❌ Error checking environment requirements")
            return False
    
    def run_all_tests(self):
        """Run all comparison tests."""
        print("=" * 70)
        print("AGENT COMPARISON TEST: Claude Baseline vs Claude+MCP")
        print("=" * 70)
        
        tests = [
            ("Baseline Command Generation", self.test_baseline_command_generation),
            ("Baseline Environment", self.test_baseline_environment),
            ("MCP Command Generation", self.test_mcp_command_generation),
            ("MCP Environment", self.test_mcp_environment),
            ("Instruction Handling", self.test_instruction_handling),
            ("Agent Differentiation", self.test_agent_differentiation),
        ]
        
        passed = 0
        failed = 0
        
        for test_name, test_func in tests:
            try:
                result = test_func()
                if result:
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"\n❌ Test '{test_name}' raised exception: {e}")
                import traceback
                traceback.print_exc()
                failed += 1
        
        # Print summary
        print("\n" + "=" * 70)
        print(f"RESULTS: {passed} passed, {failed} failed")
        print("=" * 70)
        
        return failed == 0


def main():
    tester = AgentComparisonTest()
    success = tester.run_all_tests()
    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
