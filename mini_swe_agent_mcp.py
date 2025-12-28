"""
Mini SWE Agent with optional MCP (Model Context Protocol) server support.

This is a standalone agent that extends MiniSweAgent to support MCP servers
for ablation studies. It can be used with harbor via --agent-import-path.

Usage:
    # Without MCP (baseline):
    harbor trials start \\
        --agent-import-path mini_swe_agent_mcp:MiniSweAgentMCP \\
        -m anthropic/claude-sonnet-4 \\
        -p path/to/task

    # With Sourcegraph MCP:
    harbor trials start \\
        --agent-import-path mini_swe_agent_mcp:MiniSweAgentMCP \\
        -m anthropic/claude-sonnet-4 \\
        -p path/to/task \\
        --agent-kwarg 'mcp_servers={"sourcegraph":{"command":"npx","args":["-y","@sourcegraph/cody"]}}'

    # With Deep Search MCP (example):
    harbor trials start \\
        --agent-import-path mini_swe_agent_mcp:MiniSweAgentMCP \\
        -m anthropic/claude-sonnet-4 \\
        -p path/to/task \\
        --agent-kwarg 'mcp_servers={"deepsearch":{"command":"uvx","args":["mcp-server-fetch"]}}'
"""
import json
import os
import shlex
from pathlib import Path
from typing import Any

# Import from the installed harbor package
from harbor.agents.installed.base import BaseInstalledAgent, ExecInput
from harbor.agents.utils import get_api_key_var_names_from_model_name
from harbor.models.agent.context import AgentContext
from harbor.models.trial.paths import EnvironmentPaths


class MiniSweAgentMCP(BaseInstalledAgent):
    """
    Mini SWE Agent with optional MCP server support.

    Inherits the base mini-swe-agent functionality and adds optional MCP server
    configuration. MCP servers provide additional context to the agent (e.g.,
    code search via Sourcegraph, web search via Deep Search).
    """

    SUPPORTS_ATIF: bool = True

    def __init__(
        self,
        logs_dir: Path,
        mcp_servers: dict[str, dict] | str | None = None,
        version: str | None = None,
        *args,
        **kwargs
    ):
        """
        Initialize Mini SWE Agent with optional MCP servers.

        Args:
            logs_dir: Directory for logs
            mcp_servers: Optional MCP server configurations. Can be:
                - dict: {"server_name": {"command": "...", "args": [...], "env": {...}}}
                - str: JSON string of the above format
                - None: No MCP servers (baseline mode)
            version: Version of mini-swe-agent to install
            *args, **kwargs: Additional arguments passed to parent class
        """
        super().__init__(logs_dir, *args, **kwargs)
        self._version = version

        # Parse mcp_servers if it's a string (from CLI --agent-kwarg)
        if isinstance(mcp_servers, str):
            try:
                self.mcp_servers = json.loads(mcp_servers)
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"Invalid mcp_servers JSON. Expected format: "
                    f'{{"server_name":{{"command":"...","args":[...]}}}}. Error: {e}'
                )
        else:
            self.mcp_servers = mcp_servers or {}

    @staticmethod
    def name() -> str:
        return "mini-swe-agent-mcp"

    @property
    def _install_agent_template_path(self) -> Path:
        # Use custom ARM64-compatible installation script (avoids uv segfault on Apple Silicon)
        custom_template = Path(__file__).parent / "install-mini-swe-agent-arm64.sh.j2"
        if custom_template.exists():
            return custom_template

        # Fallback to the standard mini-swe-agent template
        import harbor.agents.installed.mini_swe_agent as mini_module
        return Path(mini_module.__file__).parent / "install-mini-swe-agent.sh.j2"

    def version(self) -> str | None:
        return self._version

    def _create_mcp_config_file(self, config_path: Path) -> str:
        """Create MCP configuration file and return the command to write it.

        Supports both command-based and HTTP-based MCP servers:
        - Command-based: {"command": "...", "args": [...], "env": {...}}
        - HTTP-based: {"type": "http", "url": "...", "headers": {...}}
        """
        if not self.mcp_servers:
            return ""

        mcp_config = {"mcpServers": {}}

        for server_name, server_config in self.mcp_servers.items():
            # Check if it's HTTP-based or command-based
            if server_config.get("type") == "http":
                # HTTP-based MCP server (e.g., Sourcegraph)
                mcp_config["mcpServers"][server_name] = {
                    "type": "http",
                    "url": server_config.get("url", ""),
                    "headers": server_config.get("headers", {}),
                }
            else:
                # Command-based MCP server (e.g., npx)
                mcp_config["mcpServers"][server_name] = {
                    "command": server_config.get("command", ""),
                    "args": server_config.get("args", []),
                }
                # Add env vars if specified
                if "env" in server_config:
                    mcp_config["mcpServers"][server_name]["env"] = server_config["env"]

        # Create the command to write the config file
        config_json = json.dumps(mcp_config, indent=2)
        escaped_json = config_json.replace("'", "'\\''")

        return f"echo '{escaped_json}' > {config_path}"

    def populate_context_post_run(self, context: AgentContext) -> None:
        """
        Populate context from mini-swe-agent trajectory file.
        This is copied from the base MiniSweAgent implementation.
        """
        from harbor.agents.installed.mini_swe_agent import convert_and_save_trajectory
        import uuid

        # Read the mini-swe-agent trajectory
        mini_trajectory_path = self.logs_dir / "mini-swe-agent.trajectory.json"

        if not mini_trajectory_path.exists():
            print(
                f"Mini-swe-agent trajectory file {mini_trajectory_path} does not exist"
            )
            return

        try:
            mini_trajectory = json.loads(mini_trajectory_path.read_text())
        except Exception as e:
            print(f"Failed to load mini-swe-agent trajectory: {e}")
            return

        # Extract token usage from mini-swe-agent format
        n_input_tokens = 0
        n_output_tokens = 0
        n_cache_tokens = 0
        total_cost = ((mini_trajectory.get("info") or {}).get("model_stats") or {}).get(
            "instance_cost"
        ) or 0
        for message in mini_trajectory.get("messages") or []:
            usage = ((message.get("extra") or {}).get("response") or {}).get(
                "usage"
            ) or {}

            prompt_tokens_details = usage.get("prompt_tokens_details") or {}
            n_cache_tokens += prompt_tokens_details.get("cached_tokens") or 0

            n_input_tokens += usage.get("prompt_tokens") or 0
            n_output_tokens += usage.get("completion_tokens") or 0

        context.n_input_tokens = n_input_tokens
        context.n_output_tokens = n_output_tokens
        context.n_cache_tokens = n_cache_tokens
        context.cost_usd = total_cost

        # Convert mini-swe-agent trajectory to ATIF format
        atif_trajectory_path = self.logs_dir / "trajectory.json"
        session_id = str(uuid.uuid4())
        try:
            convert_and_save_trajectory(
                mini_swe_agent_trajectory_path=mini_trajectory_path,
                atif_trajectory_path=atif_trajectory_path,
                session_id=session_id,
            )
        except Exception as e:
            print(f"Failed to convert trajectory to ATIF format: {e}")

    def create_run_agent_commands(self, instruction: str) -> list[ExecInput]:
        """Create commands to run mini-swe-agent with optional MCP support."""
        escaped_instruction = shlex.quote(instruction)

        if not self.model_name or "/" not in self.model_name:
            raise ValueError("Model name must be in the format provider/model_name")

        env = {
            "MSWEA_CONFIGURED": "true",  # Disable interactive setup
        }

        # Set up API key
        if "MSWEA_API_KEY" in os.environ:
            env["MSWEA_API_KEY"] = os.environ["MSWEA_API_KEY"]
        else:
            try:
                api_key_var = get_api_key_var_names_from_model_name(self.model_name)
                if api_key_var in os.environ:
                    env[api_key_var] = os.environ[api_key_var]
                else:
                    raise ValueError(
                        f"No API key found for model {self.model_name}. "
                        f"Please set {api_key_var} or MSWEA_API_KEY environment variable"
                    )
            except ValueError as e:
                raise ValueError(
                    f"Unable to determine API key for model {self.model_name}: {e}. "
                    "Please set MSWEA_API_KEY environment variable as fallback"
                )

        commands = []

        # If MCP servers are configured, set them up
        if self.mcp_servers:
            mcp_config_path = EnvironmentPaths.agent_dir / "mcp_config.json"

            # Create MCP config file command
            create_config_cmd = self._create_mcp_config_file(mcp_config_path)

            commands.append(
                ExecInput(
                    command=create_config_cmd,
                    env=env,
                )
            )

            # Log which MCP servers are configured
            server_names = ", ".join(self.mcp_servers.keys())
            commands.append(
                ExecInput(
                    command=f"echo 'MCP servers configured: {server_names}' | tee /logs/agent/mcp-setup.txt",
                    env=env,
                )
            )

            # Set environment variable pointing to MCP config
            # Note: mini-swe-agent doesn't natively support MCP yet, so this prepares
            # the config for when it does, or for wrapper scripts that can use it
            env["MINI_SWE_AGENT_MCP_CONFIG"] = str(mcp_config_path)

        # Run mini-swe-agent (same as base implementation)
        commands.append(
            ExecInput(
                command=(
                    f"mini-swe-agent -m {self.model_name} -t {escaped_instruction} -y "
                    f"-o {EnvironmentPaths.agent_dir / 'mini-swe-agent.trajectory.json'} -l 0 "
                    f"--exit-immediately 2>&1 </dev/null | tee /logs/agent/mini-swe-agent.txt"
                ),
                env=env,
            )
        )

        return commands


# Convenience: Also export a simpler baseline alias
MiniSweAgentBaseline = MiniSweAgentMCP


class MiniSweAgentSourcegraphMCP(MiniSweAgentMCP):
    """Mini SWE Agent with Sourcegraph MCP (all tools: keyword, NLS, Deep Search).

    Uses HTTP-based Sourcegraph MCP endpoint for full code intelligence.
    Requires SOURCEGRAPH_URL and SOURCEGRAPH_ACCESS_TOKEN environment variables.
    """

    def __init__(self, logs_dir: Path, *args, **kwargs):
        # Get Sourcegraph credentials from environment
        sg_url = os.environ.get("SOURCEGRAPH_URL", "")
        sg_token = os.environ.get("SOURCEGRAPH_ACCESS_TOKEN", "")

        if not sg_url or not sg_token:
            raise ValueError(
                "MiniSweAgentSourcegraphMCP requires SOURCEGRAPH_URL and "
                "SOURCEGRAPH_ACCESS_TOKEN environment variables"
            )

        if not sg_url.startswith(("http://", "https://")):
            sg_url = f"https://{sg_url}"
        sg_url = sg_url.rstrip("/")

        # Configure HTTP-based Sourcegraph MCP
        mcp_servers = {
            "sourcegraph": {
                "type": "http",
                "url": f"{sg_url}/.api/mcp/v1",
                "headers": {"Authorization": f"token {sg_token}"},
            }
        }

        super().__init__(logs_dir, mcp_servers=mcp_servers, *args, **kwargs)


class MiniSweAgentDeepSearchMCP(MiniSweAgentMCP):
    """Mini SWE Agent with Deep Search MCP only (focused semantic search).

    Uses HTTP-based Deep Search MCP endpoint for semantic code search.
    Requires SOURCEGRAPH_URL and SOURCEGRAPH_ACCESS_TOKEN environment variables.
    """

    def __init__(self, logs_dir: Path, *args, **kwargs):
        # Get Sourcegraph credentials from environment
        sg_url = os.environ.get("SOURCEGRAPH_URL", "")
        sg_token = os.environ.get("SOURCEGRAPH_ACCESS_TOKEN", "")

        if not sg_url or not sg_token:
            raise ValueError(
                "MiniSweAgentDeepSearchMCP requires SOURCEGRAPH_URL and "
                "SOURCEGRAPH_ACCESS_TOKEN environment variables"
            )

        if not sg_url.startswith(("http://", "https://")):
            sg_url = f"https://{sg_url}"
        sg_url = sg_url.rstrip("/")

        # Configure HTTP-based Deep Search MCP endpoint
        mcp_servers = {
            "deepsearch": {
                "type": "http",
                "url": f"{sg_url}/.api/mcp/deepsearch",
                "headers": {"Authorization": f"token {sg_token}"},
            }
        }

        super().__init__(logs_dir, mcp_servers=mcp_servers, *args, **kwargs)


# Export all variants for easy discovery
__all__ = [
    "MiniSweAgentMCP",
    "MiniSweAgentBaseline",
    "MiniSweAgentSourcegraphMCP",
    "MiniSweAgentDeepSearchMCP",
]
