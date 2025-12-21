"""Tests for MCP agent variants (CodeContextBench-1md).

Tests the three agent variants:
1. DeepSearchFocusedAgent - Emphasizes Deep Search
2. MCPNonDeepSearchAgent - MCP without Deep Search
3. FullToolkitAgent - All tools, neutral prompting
"""

import pytest

try:
    from agents.mcp_variants import (
        DeepSearchFocusedAgent,
        MCPNonDeepSearchAgent,
        FullToolkitAgent,
    )
    HARBOR_AVAILABLE = True
except ImportError as e:
    HARBOR_AVAILABLE = False
    HARBOR_SKIP_REASON = f"Harbor not available: {e}"


# Test the prompt content directly without needing Harbor imports
class TestDeepSearchPromptContent:
    """Tests for DeepSearch agent prompt content."""

    def test_deep_search_prompt_file_exists(self):
        """The mcp_variants.py file should exist and be readable."""
        from pathlib import Path
        variants_path = Path(__file__).parent.parent / "agents" / "mcp_variants.py"
        assert variants_path.exists(), "agents/mcp_variants.py should exist"
        content = variants_path.read_text()
        assert "DeepSearchFocusedAgent" in content
        assert "MCPNonDeepSearchAgent" in content
        assert "FullToolkitAgent" in content

    def test_deep_search_prompt_content(self):
        """Deep Search system prompt should emphasize Deep Search."""
        from pathlib import Path
        content = (Path(__file__).parent.parent / "agents" / "mcp_variants.py").read_text()

        # Should mention sg_deepsearch
        assert "sg_deepsearch" in content
        # Should emphasize using it first/primary
        assert "FIRST" in content or "PRIMARY" in content
        # Should have CLAUDE.md guidance
        assert "CLAUDE_MD" in content

    def test_non_deepsearch_prompt_content(self):
        """Non-Deep Search agent should discourage Deep Search."""
        from pathlib import Path
        content = (Path(__file__).parent.parent / "agents" / "mcp_variants.py").read_text()

        # Should have the non-deep search class
        assert "MCPNonDeepSearchAgent" in content
        # Should mention keyword and NLS search
        assert "sg_keyword_search" in content
        assert "sg_nls_search" in content
        # Should say Deep Search is not available
        assert "DO NOT USE" in content or "disabled" in content.lower()

    def test_full_toolkit_prompt_content(self):
        """Full toolkit agent should be neutral."""
        from pathlib import Path
        content = (Path(__file__).parent.parent / "agents" / "mcp_variants.py").read_text()

        # Should have the full toolkit class
        assert "FullToolkitAgent" in content
        # Should mention all tools neutrally
        assert "NEUTRAL_SYSTEM_PROMPT" in content
        # Should not push any specific approach
        assert "Choose" in content or "best tool" in content.lower()


@pytest.mark.skipif(not HARBOR_AVAILABLE, reason="Harbor not available")
class TestDeepSearchFocusedAgent:
    """Tests for DeepSearchFocusedAgent (requires Harbor)."""

    def test_system_prompt_emphasizes_deep_search(self):
        """System prompt should heavily emphasize Deep Search."""
        prompt = DeepSearchFocusedAgent.DEEP_SEARCH_SYSTEM_PROMPT

        assert "sg_deepsearch" in prompt
        assert "FIRST" in prompt or "PRIMARY" in prompt

    def test_claude_md_has_deep_search_guidance(self):
        """CLAUDE.md should guide toward Deep Search."""
        claude_md = DeepSearchFocusedAgent.DEEP_SEARCH_CLAUDE_MD

        assert "Deep Search" in claude_md or "sg_deepsearch" in claude_md
        assert "AVOID" in claude_md or "avoid" in claude_md.lower()

    def test_class_has_required_methods(self):
        """Agent class should have required Harbor methods."""
        assert hasattr(DeepSearchFocusedAgent, "create_run_agent_commands")
        assert hasattr(DeepSearchFocusedAgent, "setup")


@pytest.mark.skipif(not HARBOR_AVAILABLE, reason="Harbor not available")
class TestMCPNonDeepSearchAgent:
    """Tests for MCPNonDeepSearchAgent (requires Harbor)."""

    def test_system_prompt_excludes_deep_search(self):
        """System prompt should discourage Deep Search."""
        prompt = MCPNonDeepSearchAgent.NON_DEEPSEARCH_SYSTEM_PROMPT

        assert "sg_keyword_search" in prompt
        assert "sg_nls_search" in prompt
        assert "DO NOT USE" in prompt or "disabled" in prompt.lower()

    def test_claude_md_mentions_disabled_tools(self):
        """CLAUDE.md should note Deep Search is unavailable."""
        claude_md = MCPNonDeepSearchAgent.NON_DEEPSEARCH_CLAUDE_MD

        assert "NOT" in claude_md or "Disabled" in claude_md or "❌" in claude_md

    def test_class_has_required_methods(self):
        """Agent class should have required Harbor methods."""
        assert hasattr(MCPNonDeepSearchAgent, "create_run_agent_commands")
        assert hasattr(MCPNonDeepSearchAgent, "setup")


@pytest.mark.skipif(not HARBOR_AVAILABLE, reason="Harbor not available")
class TestFullToolkitAgent:
    """Tests for FullToolkitAgent (requires Harbor)."""

    def test_system_prompt_is_neutral(self):
        """System prompt should list tools without preference."""
        prompt = FullToolkitAgent.NEUTRAL_SYSTEM_PROMPT

        assert "sg_deepsearch" in prompt
        assert "sg_nls_search" in prompt
        assert "sg_keyword_search" in prompt
        assert "MUST use Deep Search" not in prompt

    def test_claude_md_is_neutral(self):
        """CLAUDE.md should be neutral about tool choice."""
        claude_md = FullToolkitAgent.NEUTRAL_CLAUDE_MD

        assert "sg_deepsearch" in claude_md
        assert "sg_keyword_search" in claude_md
        assert "Choose" in claude_md or "best tool" in claude_md.lower()

    def test_class_has_required_methods(self):
        """Agent class should have required Harbor methods."""
        assert hasattr(FullToolkitAgent, "create_run_agent_commands")
        assert hasattr(FullToolkitAgent, "setup")


@pytest.mark.skipif(not HARBOR_AVAILABLE, reason="Harbor not available")
class TestAgentVariantDifferences:
    """Tests that variants are meaningfully different (requires Harbor)."""

    def test_prompts_are_distinct(self):
        """Each variant should have distinct prompts."""
        prompts = [
            DeepSearchFocusedAgent.DEEP_SEARCH_SYSTEM_PROMPT,
            MCPNonDeepSearchAgent.NON_DEEPSEARCH_SYSTEM_PROMPT,
            FullToolkitAgent.NEUTRAL_SYSTEM_PROMPT,
        ]
        assert len(set(prompts)) == 3, "All three prompts should be distinct"

    def test_claude_mds_are_distinct(self):
        """Each variant should have distinct CLAUDE.md content."""
        claude_mds = [
            DeepSearchFocusedAgent.DEEP_SEARCH_CLAUDE_MD,
            MCPNonDeepSearchAgent.NON_DEEPSEARCH_CLAUDE_MD,
            FullToolkitAgent.NEUTRAL_CLAUDE_MD,
        ]
        assert len(set(claude_mds)) == 3, "All three CLAUDE.md should be distinct"

    def test_deep_search_focused_is_most_emphatic(self):
        """DeepSearchFocusedAgent should be most emphatic about Deep Search."""
        deep_count = DeepSearchFocusedAgent.DEEP_SEARCH_SYSTEM_PROMPT.lower().count("deep")
        full_count = FullToolkitAgent.NEUTRAL_SYSTEM_PROMPT.lower().count("deep")

        assert deep_count > full_count, "DeepSearch agent should emphasize deep search more"
