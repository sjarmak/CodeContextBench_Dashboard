"""MCP Agent Variants for A/B testing tool combinations.

Four variants to isolate the value of different tool combinations:
1. DeepSearchFocusedAgent - Heavily emphasizes Deep Search tool usage (aggressive)
2. StrategicDeepSearchAgent - Uses Deep Search strategically for context-gathering
3. MCPNonDeepSearchAgent - MCP tools (keyword, NLS) but NOT Deep Search
4. FullToolkitAgent - All tools available, neutral prompting

Reference: CodeContextBench-1md - Optimize MCP agent with three variants
Reference: CodeContextBench-6pl - MCP prompt experiment: strategic vs aggressive
"""

import json
import os
from pathlib import Path
from typing import Any

from harbor.agents.installed.claude_code import ClaudeCode
from harbor.agents.installed.base import ExecInput
from harbor.environments.base import BaseEnvironment
from harbor.models.trial.paths import EnvironmentPaths


class StrategicDeepSearchAgent(ClaudeCode):
    """MCP agent that uses Deep Search STRATEGICALLY for context-gathering.

    Philosophy: Deep Search is for gathering context at key moments, not
    for every micro-question. One good Deep Search call should inform
    many subsequent decisions.

    WHEN to use Deep Search:
    - At task start: understand architecture and relevant subsystems
    - When hitting information gaps: new subsystem, unclear dependencies
    - Before major implementation decisions

    WHEN NOT to use Deep Search:
    - For every small question (leverage already-gathered context)
    - When you already have the file open
    - For simple lookups after initial context gathering

    Reference: CodeContextBench-6pl
    """

    STRATEGIC_SYSTEM_PROMPT = """You MUST complete this coding task by making actual code changes.

## Sourcegraph Deep Search - Use Strategically

You have access to **Sourcegraph Deep Search** (`sg_deepsearch`) via MCP. This is a powerful context-gathering tool - use it wisely.

### WHEN to use Deep Search (Strategic Moments)

1. **At Task Start**: Before any code changes, use Deep Search to understand:
   - The architecture of the relevant subsystem
   - How components interact
   - Existing patterns and conventions

2. **When You Hit an Information Gap**: Use Deep Search when you encounter:
   - An unfamiliar subsystem or module
   - Unclear dependencies between components
   - Need to understand cross-file relationships

3. **Before Major Decisions**: Before implementing a significant change, verify your understanding.

### WHEN NOT to use Deep Search

❌ For every small question - leverage the context you already gathered
❌ When you already have the relevant file open
❌ For simple string lookups (use `sg_keyword_search` instead)
❌ After you already understand the architecture

### The Deep Search Workflow

1. **Gather Context First**: One comprehensive Deep Search query at task start
2. **Work with That Context**: Make multiple decisions based on gathered knowledge
3. **Deep Search Again Only When Blocked**: If you hit a wall, new subsystem, or unexpected complexity

### Example: Good vs Bad Usage

**GOOD**:
- "Before I start, let me understand the diagnostics pipeline architecture" → sg_deepsearch
- (Make 10 edits based on that understanding)
- "I need to modify error handling but don't understand this new subsystem" → sg_deepsearch

**BAD**:
- Use Deep Search → understand one function → Deep Search again for next function → etc.
- Using Deep Search when you already have the file open and can just read it

## Implementation Requirements

1. Use Deep Search at the start to understand the problem space
2. Make targeted code changes based on that understanding
3. Only use Deep Search again when you hit a genuine information gap
4. MAKE ACTUAL CODE CHANGES - this is not a planning task
"""

    STRATEGIC_CLAUDE_MD = """# MANDATORY: Use Sourcegraph MCP Tools

## YOU MUST USE MCP TOOLS - DO NOT SKIP THIS

You have Sourcegraph MCP tools configured. **Your first action MUST be to call an MCP tool.**

## Available MCP Tools (use the mcp__ prefix)

- `mcp__sourcegraph__sg_deepsearch` - **USE THIS FIRST** - Deep semantic search
- `mcp__sourcegraph__sg_keyword_search` - Exact string matching  
- `mcp__sourcegraph__sg_nls_search` - Natural language search
- `mcp__sourcegraph__sg_read_file` - Read file from indexed repo

## REQUIRED First Action

Before using Bash, Read, or Grep, you MUST call:

```
mcp__sourcegraph__sg_deepsearch with query about the bug/feature
```

Example for a TypeError bug:
```
mcp__sourcegraph__sg_deepsearch(query="TypeError combine_vars VarsWithSources implementation")
```

## Strategic Usage Pattern

1. **START**: Call `mcp__sourcegraph__sg_deepsearch` to understand the codebase
2. **THEN**: Use local Read to examine specific files identified
3. **IMPLEMENT**: Make targeted code changes
4. **IF BLOCKED**: Call MCP again for new context

## Why MCP First?

- The codebase is indexed in Sourcegraph - MCP has full cross-file understanding
- Local grep/read is limited to pattern matching
- MCP understands semantic relationships between code

## Anti-Patterns (DO NOT DO)

❌ Starting with local Bash/Grep without MCP first
❌ Reading files one-by-one to "explore"
❌ Skipping MCP because "I'll just grep for it"

## Anti-Patterns

❌ Deep Search → one edit → Deep Search → one edit (too granular)
❌ Using Deep Search for things you already understand
❌ Skipping initial context gathering and diving into edits
"""

    def create_run_agent_commands(self, instruction: str) -> list[ExecInput]:
        """Override to enable implementation mode with strategic Deep Search."""
        parent_commands = super().create_run_agent_commands(instruction)
        # Include MCP tools for Sourcegraph integration
        base_tools = "Bash,Read,Edit,Write,Grep,Glob,Skill,TodoWrite,Task,TaskOutput"
        mcp_tools = "mcp__sourcegraph__sg_deepsearch,mcp__sourcegraph__sg_keyword_search,mcp__sourcegraph__sg_nls_search,mcp__sourcegraph__sg_read_file,mcp__deepsearch__deepsearch"
        allowed_tools = f"{base_tools},{mcp_tools}"

        result = []
        for cmd in parent_commands:
            if cmd.command and "claude " in cmd.command:
                modified_command = cmd.command.replace(
                    "claude ",
                    f"claude --permission-mode acceptEdits --allowedTools {allowed_tools} ",
                )
                env = cmd.env or {}
                env_with_autonomous = {
                    **env,
                    "FORCE_AUTO_BACKGROUND_TASKS": "1",
                    "ENABLE_BACKGROUND_TASKS": "1",
                }
                self.logger.info(
                    "StrategicDeepSearchAgent: Implementation mode with strategic Deep Search"
                )
                result.append(
                    ExecInput(command=modified_command, env=env_with_autonomous)
                )
            else:
                result.append(cmd)
        return result

    async def setup(self, environment: BaseEnvironment) -> None:
        """Setup with strategic Deep Search prompts."""
        sg_url = (
            os.environ.get("SOURCEGRAPH_URL") or os.environ.get("SRC_ENDPOINT") or ""
        )
        sg_token = (
            os.environ.get("SOURCEGRAPH_ACCESS_TOKEN")
            or os.environ.get("SRC_ACCESS_TOKEN")
            or ""
        )

        if sg_url and sg_token:
            if not sg_url.startswith(("http://", "https://")):
                sg_url = f"https://{sg_url}"
            sg_url = sg_url.rstrip("/")

            # Full MCP config with all Sourcegraph tools
            mcp_config = {
                "mcpServers": {
                    "sourcegraph": {
                        "type": "http",
                        "url": f"{sg_url}/.api/mcp/v1",
                        "headers": {"Authorization": f"token {sg_token}"},
                    }
                }
            }

            mcp_config_path = self.logs_dir / ".mcp.json"
            with open(mcp_config_path, "w") as f:
                json.dump(mcp_config, f, indent=2)

            # Upload to /app/ (working directory)
            await environment.upload_file(
                source_path=mcp_config_path, target_path="/app/.mcp.json"
            )
            # Also upload to home config directory for Claude Code discovery
            await environment.upload_file(
                source_path=mcp_config_path, target_path="/root/.mcp.json"
            )
            self.logger.info("✓ StrategicDeepSearchAgent: MCP config uploaded to /app/ and /root/")

            # Upload strategic system prompt
            system_prompt_path = self.logs_dir / "system_prompt.txt"
            with open(system_prompt_path, "w") as f:
                f.write(self.STRATEGIC_SYSTEM_PROMPT)

            await environment.upload_file(
                source_path=system_prompt_path,
                target_path="/app/system_prompt.txt",
            )
            self.logger.info(
                "✓ StrategicDeepSearchAgent: Strategic system prompt uploaded"
            )

            # Upload strategic CLAUDE.md
            claude_md_path = self.logs_dir / "CLAUDE.md"
            with open(claude_md_path, "w") as f:
                f.write(self.STRATEGIC_CLAUDE_MD)

            await environment.upload_file(
                source_path=claude_md_path, target_path="/app/CLAUDE.md"
            )
            self.logger.info("✓ StrategicDeepSearchAgent: Strategic CLAUDE.md uploaded")
        else:
            self.logger.warning(
                "⚠ StrategicDeepSearchAgent: Sourcegraph credentials not configured"
            )

        await super().setup(environment)


class DeepSearchFocusedAgent(ClaudeCode):
    """MCP agent that heavily emphasizes Deep Search tool usage.

    System prompt explicitly instructs to use sg_deepsearch for all
    code understanding tasks. This variant tests whether prompting
    for Deep Search improves outcomes.

    Key differences from baseline MCP agent:
    - System prompt prioritizes Deep Search over local tools
    - CLAUDE.md contains aggressive guidance to use Deep Search first
    - Metrics: Expect higher Deep Search call count, lower token waste
    """

    DEEP_SEARCH_SYSTEM_PROMPT = """You MUST complete this coding task by making actual code changes.

## CRITICAL: Use Sourcegraph Deep Search FIRST

You have access to **Sourcegraph Deep Search** via MCP. This is your PRIMARY tool for understanding code.

**ALWAYS use Deep Search (`sg_deepsearch`) BEFORE any local search tools when:**
- Understanding code architecture or patterns
- Finding all usages of a function/class/variable
- Tracing data flow across files
- Understanding how components interact
- Finding similar code patterns
- Answering "where is X used?" or "how does X work?"

**WHY Deep Search?**
- Faster than reading files one-by-one
- Understands semantic relationships (not just text matching)
- Can search across the entire codebase in one query
- Provides context-aware results

**Local tools (Grep, Glob, Read) are for:**
- Reading specific files you already identified
- Making edits to files
- Running commands

## Implementation Requirements

This is not a planning or analysis task. You must:
1. Use Deep Search to understand the problem domain
2. Use Deep Search to find all relevant code locations
3. MAKE ACTUAL CODE CHANGES to implement the fix or feature
4. Test your implementation

CRITICAL: Use `sg_deepsearch` for every code understanding question. Do not skip to local grep/read.
"""

    DEEP_SEARCH_CLAUDE_MD = """# CRITICAL: Use MCP Tools - DO NOT USE LOCAL GREP/BASH FIRST

## YOUR FIRST ACTION MUST BE AN MCP TOOL CALL

You have Sourcegraph MCP configured. **You MUST call an MCP tool before any local tool.**

## MCP Tool Names (use exactly these names)

- `mcp__sourcegraph__sg_deepsearch` - **CALL THIS FIRST** - Deep semantic search
- `mcp__sourcegraph__sg_keyword_search` - Exact string matching
- `mcp__sourcegraph__sg_nls_search` - Natural language search
- `mcp__sourcegraph__sg_read_file` - Read indexed file

## MANDATORY First Step

Your FIRST tool call must be:
```
mcp__sourcegraph__sg_deepsearch(query="<describe the bug or feature>")
```

Example:
```
mcp__sourcegraph__sg_deepsearch(query="TypeError combine_vars VarsWithSources dict handling")
```

## Why MCP First?

1. The entire codebase is indexed in Sourcegraph
2. MCP understands semantic code relationships
3. Local grep only does pattern matching
4. MCP saves time by finding the right code immediately

## FORBIDDEN Actions (DO NOT DO THESE FIRST)

❌ `Bash("grep ...")` - Do not grep before MCP
❌ `Bash("find ...")` - Do not find before MCP  
❌ `Read("some/file.py")` - Do not read random files before MCP
❌ `Glob("**/*.py")` - Do not glob before MCP

## Correct Workflow

1. **FIRST**: `mcp__sourcegraph__sg_deepsearch(query="...")`
2. **THEN**: Read specific files from MCP results
3. **THEN**: Make targeted code changes
4. **IF STUCK**: Call MCP again with refined query
2. FIRST: `sg_deepsearch("authentication bug handling error flow")`
3. THEN: Read the specific files Deep Search identified
4. THEN: Make targeted edits
5. THEN: Test

Remember: Deep Search saves tokens by finding the right code faster.
"""

    def create_run_agent_commands(self, instruction: str) -> list[ExecInput]:
        """Override to enable implementation mode with Deep Search emphasis."""
        parent_commands = super().create_run_agent_commands(instruction)
        # Include MCP tools for Sourcegraph integration
        base_tools = "Bash,Read,Edit,Write,Grep,Glob,Skill,TodoWrite,Task,TaskOutput"
        mcp_tools = "mcp__sourcegraph__sg_deepsearch,mcp__sourcegraph__sg_keyword_search,mcp__sourcegraph__sg_nls_search,mcp__sourcegraph__sg_read_file,mcp__deepsearch__deepsearch"
        allowed_tools = f"{base_tools},{mcp_tools}"

        result = []
        for cmd in parent_commands:
            if cmd.command and "claude " in cmd.command:
                modified_command = cmd.command.replace(
                    "claude ",
                    f"claude --permission-mode acceptEdits --allowedTools {allowed_tools} ",
                )
                env = cmd.env or {}
                env_with_autonomous = {
                    **env,
                    "FORCE_AUTO_BACKGROUND_TASKS": "1",
                    "ENABLE_BACKGROUND_TASKS": "1",
                }
                self.logger.info(
                    "DeepSearchFocusedAgent: Implementation mode with Deep Search emphasis"
                )
                result.append(
                    ExecInput(command=modified_command, env=env_with_autonomous)
                )
            else:
                result.append(cmd)
        return result

    async def setup(self, environment: BaseEnvironment) -> None:
        """Setup with Deep Search focused prompts using Deep Search MCP endpoint."""
        # Check for dedicated Deep Search MCP endpoint first
        deepsearch_url = os.environ.get("DEEPSEARCH_MCP_URL") or ""
        deepsearch_token = os.environ.get("DEEPSEARCH_MCP_TOKEN") or ""
        
        # Fall back to Sourcegraph if no dedicated endpoint
        if not deepsearch_url:
            sg_url = (
                os.environ.get("SOURCEGRAPH_URL") or os.environ.get("SRC_ENDPOINT") or ""
            )
            sg_token = (
                os.environ.get("SOURCEGRAPH_ACCESS_TOKEN")
                or os.environ.get("SRC_ACCESS_TOKEN")
                or ""
            )
            if sg_url and sg_token:
                if not sg_url.startswith(("http://", "https://")):
                    sg_url = f"https://{sg_url}"
                deepsearch_url = sg_url.rstrip("/") + "/.api/mcp/deepsearch"
                deepsearch_token = sg_token
        
        if deepsearch_url and deepsearch_token:
            if not deepsearch_url.startswith(("http://", "https://")):
                deepsearch_url = f"https://{deepsearch_url}"
            deepsearch_url = deepsearch_url.rstrip("/")

            # Deep Search MCP endpoint config
            mcp_config = {
                "mcpServers": {
                    "deepsearch": {
                        "type": "http",
                        "url": deepsearch_url,
                        "headers": {"Authorization": f"token {deepsearch_token}"},
                    }
                }
            }

            mcp_config_path = self.logs_dir / ".mcp.json"
            with open(mcp_config_path, "w") as f:
                json.dump(mcp_config, f, indent=2)

            # Upload to /app/ (working directory)
            await environment.upload_file(
                source_path=mcp_config_path, target_path="/app/.mcp.json"
            )
            # Also upload to home for Claude Code discovery
            await environment.upload_file(
                source_path=mcp_config_path, target_path="/root/.mcp.json"
            )
            self.logger.info(f"✓ DeepSearchFocusedAgent: Deep Search MCP configured at /app/ and /root/ ({deepsearch_url})")

            # Upload Deep Search focused system prompt
            system_prompt_path = self.logs_dir / "system_prompt.txt"
            with open(system_prompt_path, "w") as f:
                f.write(self.DEEP_SEARCH_SYSTEM_PROMPT)

            await environment.upload_file(
                source_path=system_prompt_path,
                target_path="/app/system_prompt.txt",
            )
            self.logger.info(
                "✓ DeepSearchFocusedAgent: System prompt with Deep Search emphasis uploaded"
            )

            # Upload aggressive CLAUDE.md
            claude_md_path = self.logs_dir / "CLAUDE.md"
            with open(claude_md_path, "w") as f:
                f.write(self.DEEP_SEARCH_CLAUDE_MD)

            await environment.upload_file(
                source_path=claude_md_path, target_path="/app/CLAUDE.md"
            )
            self.logger.info(
                "✓ DeepSearchFocusedAgent: CLAUDE.md with Deep Search guidance uploaded"
            )
        else:
            self.logger.warning(
                "⚠ DeepSearchFocusedAgent: Sourcegraph credentials not configured"
            )

        await super().setup(environment)


class MCPNonDeepSearchAgent(ClaudeCode):
    """MCP agent with keyword/NLS search but NOT Deep Search.

    Tests the value of MCP without the Deep Search tool specifically.
    Uses sg_keyword_search and sg_nls_search but explicitly avoids
    or disables sg_deepsearch.

    Key differences:
    - System prompt guides toward keyword and NLS search
    - CLAUDE.md warns against using sg_deepsearch (if available)
    - Tests whether simpler MCP tools are sufficient
    """

    NON_DEEPSEARCH_SYSTEM_PROMPT = """You MUST complete this coding task by making actual code changes.

## MCP Search Tools Available

You have Sourcegraph MCP with these search tools:

**USE THESE:**
- `mcp__sourcegraph__sg_keyword_search` - Fast exact string matching across the codebase
- `mcp__sourcegraph__sg_nls_search` - Natural language semantic search

**DO NOT USE:**
- `mcp__sourcegraph__sg_deepsearch` - This tool is disabled for this benchmark variant

## Search Strategy

1. For exact matches (function names, variable names, error messages):
   → Use `sg_keyword_search`

2. For conceptual questions ("how does authentication work"):
   → Use `sg_nls_search`

3. For narrow, single-directory scopes:
   → Use local Grep/Glob

## Implementation Requirements

This is not a planning or analysis task. You must:
1. Understand the problem/bug/feature requirement
2. Use MCP keyword/NLS search to locate relevant code
3. MAKE ACTUAL CODE CHANGES to implement the fix or feature
4. Test your implementation

CRITICAL: You must make actual code modifications. The task is complete only when code files have been changed.
"""

    NON_DEEPSEARCH_CLAUDE_MD = """# Sourcegraph MCP - Keyword & NLS Search

## Available Tools

✅ `mcp__sourcegraph__sg_keyword_search` - Exact string matching
✅ `mcp__sourcegraph__sg_nls_search` - Natural language queries
✅ Local Grep/Glob for directory-scoped searches

## NOT Available

❌ `mcp__sourcegraph__sg_deepsearch` - Disabled for this benchmark variant

## Usage Patterns

```
mcp__sourcegraph__sg_keyword_search(query="AuthenticationError")
mcp__sourcegraph__sg_nls_search(query="how does user login work")
```

Use keyword search for:
- Function/class/variable names
- Error messages and log strings
- Import statements
- Exact API endpoints

Use NLS search for:
- Conceptual questions
- "Where is X handled?"
- Pattern discovery
"""

    def create_run_agent_commands(self, instruction: str) -> list[ExecInput]:
        """Override to enable implementation mode."""
        parent_commands = super().create_run_agent_commands(instruction)
        # Include MCP tools for Sourcegraph integration (excluding deep search)
        base_tools = "Bash,Read,Edit,Write,Grep,Glob,Skill,TodoWrite,Task,TaskOutput"
        mcp_tools = "mcp__sourcegraph__sg_keyword_search,mcp__sourcegraph__sg_nls_search,mcp__sourcegraph__sg_read_file"
        allowed_tools = f"{base_tools},{mcp_tools}"

        result = []
        for cmd in parent_commands:
            if cmd.command and "claude " in cmd.command:
                modified_command = cmd.command.replace(
                    "claude ",
                    f"claude --permission-mode acceptEdits --allowedTools {allowed_tools} ",
                )
                env = cmd.env or {}
                env_with_autonomous = {
                    **env,
                    "FORCE_AUTO_BACKGROUND_TASKS": "1",
                    "ENABLE_BACKGROUND_TASKS": "1",
                }
                self.logger.info(
                    "MCPNonDeepSearchAgent: Implementation mode without Deep Search"
                )
                result.append(
                    ExecInput(command=modified_command, env=env_with_autonomous)
                )
            else:
                result.append(cmd)
        return result

    async def setup(self, environment: BaseEnvironment) -> None:
        """Setup with non-Deep Search MCP config."""
        sg_url = (
            os.environ.get("SOURCEGRAPH_URL") or os.environ.get("SRC_ENDPOINT") or ""
        )
        sg_token = (
            os.environ.get("SOURCEGRAPH_ACCESS_TOKEN")
            or os.environ.get("SRC_ACCESS_TOKEN")
            or ""
        )

        if sg_url and sg_token:
            if not sg_url.startswith(("http://", "https://")):
                sg_url = f"https://{sg_url}"
            sg_url = sg_url.rstrip("/")

            # MCP config - same endpoint, but prompts guide away from deep search
            # Note: We can't actually disable tools at MCP level, so we use prompting
            mcp_config = {
                "mcpServers": {
                    "sourcegraph": {
                        "type": "http",
                        "url": f"{sg_url}/.api/mcp/v1",
                        "headers": {"Authorization": f"token {sg_token}"},
                    }
                }
            }

            mcp_config_path = self.logs_dir / ".mcp.json"
            with open(mcp_config_path, "w") as f:
                json.dump(mcp_config, f, indent=2)

            # Upload to /app/ (working directory)
            await environment.upload_file(
                source_path=mcp_config_path, target_path="/app/.mcp.json"
            )
            # Also upload to home for Claude Code discovery
            await environment.upload_file(
                source_path=mcp_config_path, target_path="/root/.mcp.json"
            )
            self.logger.info("✓ MCPNonDeepSearchAgent: MCP config uploaded to /app/ and /root/")

            # Upload non-Deep Search system prompt
            system_prompt_path = self.logs_dir / "system_prompt.txt"
            with open(system_prompt_path, "w") as f:
                f.write(self.NON_DEEPSEARCH_SYSTEM_PROMPT)

            await environment.upload_file(
                source_path=system_prompt_path,
                target_path="/app/system_prompt.txt",
            )
            self.logger.info("✓ MCPNonDeepSearchAgent: System prompt uploaded")

            # Upload CLAUDE.md
            claude_md_path = self.logs_dir / "CLAUDE.md"
            with open(claude_md_path, "w") as f:
                f.write(self.NON_DEEPSEARCH_CLAUDE_MD)

            await environment.upload_file(
                source_path=claude_md_path, target_path="/app/CLAUDE.md"
            )
            self.logger.info("✓ MCPNonDeepSearchAgent: CLAUDE.md uploaded")
        else:
            self.logger.warning(
                "⚠ MCPNonDeepSearchAgent: Sourcegraph credentials not configured"
            )

        await super().setup(environment)


class FullToolkitAgent(ClaudeCode):
    """MCP agent with all tools, neutral prompting.

    Provides complete toolkit without pushing any specific approach.
    This is the "let the agent decide" baseline for comparing against
    the focused variants.

    Key differences from other variants:
    - Neutral system prompt that lists all available tools equally
    - No preference for Deep Search vs other tools
    - Agent chooses best tool for each task naturally
    """

    NEUTRAL_SYSTEM_PROMPT = """You MUST complete this coding task by making actual code changes.

## Available Tools

You have access to multiple code search and navigation tools:

**Sourcegraph MCP (cross-codebase search):**
- `sg_deepsearch` - Deep semantic search with context understanding
- `sg_nls_search` - Natural language search
- `sg_keyword_search` - Exact string matching

**Local Tools:**
- Read: Read file contents
- Edit: Modify existing files
- Write: Create new files
- Bash: Run shell commands
- Grep: Pattern matching in files
- Glob: Find files by pattern

## Implementation Requirements

This is not a planning or analysis task. You must:
1. Understand the problem/bug/feature requirement
2. Locate the relevant code files
3. MAKE ACTUAL CODE CHANGES to implement the fix or feature
4. Test your implementation

Choose the most appropriate tool for each subtask. There is no preferred approach - use whatever helps you complete the task efficiently.

CRITICAL: You must make actual code modifications. The task is complete only when code files have been changed.
"""

    NEUTRAL_CLAUDE_MD = """# Available Code Search Tools

## Sourcegraph MCP

- `sg_deepsearch` - Deep semantic search, understands code relationships
- `sg_nls_search` - Natural language queries
- `sg_keyword_search` - Exact string matching

## Local Tools

- Grep - Pattern matching
- Glob - File finding
- Read - File contents

## Usage

Choose the best tool for your task. All tools are available and equally valid choices.
"""

    def create_run_agent_commands(self, instruction: str) -> list[ExecInput]:
        """Override to enable implementation mode."""
        parent_commands = super().create_run_agent_commands(instruction)
        # Include all MCP tools for Sourcegraph integration
        base_tools = "Bash,Read,Edit,Write,Grep,Glob,Skill,TodoWrite,Task,TaskOutput"
        mcp_tools = "mcp__sourcegraph__sg_deepsearch,mcp__sourcegraph__sg_keyword_search,mcp__sourcegraph__sg_nls_search,mcp__sourcegraph__sg_read_file,mcp__deepsearch__deepsearch"
        allowed_tools = f"{base_tools},{mcp_tools}"

        result = []
        for cmd in parent_commands:
            if cmd.command and "claude " in cmd.command:
                modified_command = cmd.command.replace(
                    "claude ",
                    f"claude --permission-mode acceptEdits --allowedTools {allowed_tools} ",
                )
                env = cmd.env or {}
                env_with_autonomous = {
                    **env,
                    "FORCE_AUTO_BACKGROUND_TASKS": "1",
                    "ENABLE_BACKGROUND_TASKS": "1",
                }
                self.logger.info(
                    "FullToolkitAgent: Implementation mode with all tools, neutral prompting"
                )
                result.append(
                    ExecInput(command=modified_command, env=env_with_autonomous)
                )
            else:
                result.append(cmd)
        return result

    async def setup(self, environment: BaseEnvironment) -> None:
        """Setup with full toolkit, neutral prompts."""
        sg_url = (
            os.environ.get("SOURCEGRAPH_URL") or os.environ.get("SRC_ENDPOINT") or ""
        )
        sg_token = (
            os.environ.get("SOURCEGRAPH_ACCESS_TOKEN")
            or os.environ.get("SRC_ACCESS_TOKEN")
            or ""
        )

        if sg_url and sg_token:
            if not sg_url.startswith(("http://", "https://")):
                sg_url = f"https://{sg_url}"
            sg_url = sg_url.rstrip("/")

            # Full MCP config
            mcp_config = {
                "mcpServers": {
                    "sourcegraph": {
                        "type": "http",
                        "url": f"{sg_url}/.api/mcp/v1",
                        "headers": {"Authorization": f"token {sg_token}"},
                    }
                }
            }

            mcp_config_path = self.logs_dir / ".mcp.json"
            with open(mcp_config_path, "w") as f:
                json.dump(mcp_config, f, indent=2)

            # Upload to /app/ (working directory)
            await environment.upload_file(
                source_path=mcp_config_path, target_path="/app/.mcp.json"
            )
            # Also upload to home for Claude Code discovery
            await environment.upload_file(
                source_path=mcp_config_path, target_path="/root/.mcp.json"
            )
            self.logger.info("✓ FullToolkitAgent: MCP config uploaded to /app/ and /root/")

            # Upload neutral system prompt
            system_prompt_path = self.logs_dir / "system_prompt.txt"
            with open(system_prompt_path, "w") as f:
                f.write(self.NEUTRAL_SYSTEM_PROMPT)

            await environment.upload_file(
                source_path=system_prompt_path,
                target_path="/app/system_prompt.txt",
            )
            self.logger.info("✓ FullToolkitAgent: Neutral system prompt uploaded")

            # Upload neutral CLAUDE.md
            claude_md_path = self.logs_dir / "CLAUDE.md"
            with open(claude_md_path, "w") as f:
                f.write(self.NEUTRAL_CLAUDE_MD)

            await environment.upload_file(
                source_path=claude_md_path, target_path="/app/CLAUDE.md"
            )
            self.logger.info("✓ FullToolkitAgent: Neutral CLAUDE.md uploaded")
        else:
            self.logger.warning(
                "⚠ FullToolkitAgent: Sourcegraph credentials not configured"
            )

        await super().setup(environment)
