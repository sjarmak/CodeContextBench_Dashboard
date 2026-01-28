"""
Parse SWEBench evaluation result.json files.

This parser handles the format from SWEBenchPro evaluations which differs from
standard Harbor format in structure but contains similar information.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from datetime import datetime

from .harbor_parser import (
    HarborResult,
    HarborTaskMetadata,
    HarborAgentOutput,
    HarborVerifierResult,
)


@dataclass
class SWEBenchResult:
    """Extended result for SWEBench evaluations with MCP tracking."""
    
    # Core Harbor-compatible result
    harbor_result: HarborResult
    
    # SWEBench-specific fields
    trial_name: str = ""
    trial_uri: str = ""
    source: str = "swebenchpro"
    task_checksum: str = ""
    
    # MCP configuration (if present)
    mcp_enabled: bool = False
    mcp_servers: dict[str, Any] = field(default_factory=dict)
    
    # Timing details
    environment_setup_duration: float = 0.0
    agent_setup_duration: float = 0.0
    agent_execution_duration: float = 0.0
    verifier_duration: float = 0.0
    
    # Agent configuration
    agent_import_path: str = ""
    agent_model_name: str = ""


class SWEBenchParser:
    """Parse SWEBench evaluation results."""
    
    def parse_instance_dir(self, instance_dir: Path) -> SWEBenchResult:
        """
        Parse a complete SWEBench instance directory.
        
        Directory structure expected:
        instance_dir/
        ├── result.json         # Main result file
        ├── config.json         # Task configuration
        ├── agent/
        │   ├── claude-code.txt # Agent transcript
        │   └── .mcp.json       # MCP configuration (optional)
        └── verifier/
            ├── output.json     # Test results
            └── reward.txt      # Reward score
        """
        result_path = instance_dir / "result.json"
        if not result_path.exists():
            raise FileNotFoundError(f"No result.json in {instance_dir}")
        
        with open(result_path) as f:
            result_data = json.load(f)
        
        # Check for MCP configuration
        mcp_config = {}
        mcp_enabled = False
        mcp_path = instance_dir / "agent" / ".mcp.json"
        if mcp_path.exists():
            try:
                with open(mcp_path) as f:
                    mcp_config = json.load(f)
                    mcp_enabled = bool(mcp_config.get("mcpServers", {}))
            except Exception:
                pass
        
        # Also check sessions directory
        if not mcp_enabled:
            sessions_mcp = instance_dir / "agent" / "sessions" / ".mcp.json"
            if sessions_mcp.exists():
                try:
                    with open(sessions_mcp) as f:
                        mcp_config = json.load(f)
                        mcp_enabled = bool(mcp_config.get("mcpServers", {}))
                except Exception:
                    pass
        
        # Read reward.txt if available
        reward_raw = None
        reward_txt = instance_dir / "verifier" / "reward.txt"
        if reward_txt.exists():
            try:
                reward_raw = reward_txt.read_text().strip()
            except Exception:
                pass
        
        return self._parse_result(result_data, mcp_enabled, mcp_config, reward_raw)
    
    def parse_file(self, result_path: Path) -> HarborResult:
        """
        Parse just a result.json file (Harbor-compatible interface).
        
        Args:
            result_path: Path to result.json
            
        Returns:
            HarborResult for compatibility with existing pipeline
        """
        # Try to parse as instance directory first
        instance_dir = result_path.parent
        if (instance_dir / "agent").exists():
            swebench_result = self.parse_instance_dir(instance_dir)
            return swebench_result.harbor_result
        
        # Fall back to just parsing the result file
        with open(result_path) as f:
            result_data = json.load(f)
        
        return self._parse_result(result_data, False, {}, None).harbor_result
    
    def _parse_result(
        self,
        data: dict,
        mcp_enabled: bool,
        mcp_config: dict,
        reward_raw: Optional[str],
    ) -> SWEBenchResult:
        """Parse a SWEBench result dictionary."""
        
        # Extract task information
        task_id = self._extract_task_id(data)
        task_metadata = self._extract_task_metadata(data)
        
        # Extract timing information
        timing = self._extract_timing(data)
        
        # Extract agent output
        agent_output = self._extract_agent_output(data, timing)
        
        # Extract verifier result
        verifier_result = self._extract_verifier_result(data, reward_raw)
        
        # Determine overall pass/fail - SWEBench uses reward > 0 to indicate success
        reward_value = verifier_result.reward.get("reward", 0.0)
        passed = float(reward_value) > 0.0
        
        # Calculate total duration
        total_duration = (
            timing.get("environment_setup", 0.0) +
            timing.get("agent_setup", 0.0) +
            timing.get("agent_execution", 0.0) +
            timing.get("verifier", 0.0)
        )
        
        # Extract agent configuration
        config = data.get("config", {})
        agent_config = config.get("agent", {})
        
        harbor_result = HarborResult(
            task_id=task_id,
            task_metadata=task_metadata,
            agent_output=agent_output,
            verifier_result=verifier_result,
            passed=passed,
            duration_seconds=total_duration,
            model_name=self._extract_model_name(data),
            agent_name=self._extract_agent_name(data),
            raw_result=data,
        )
        
        return SWEBenchResult(
            harbor_result=harbor_result,
            trial_name=data.get("trial_name", ""),
            trial_uri=data.get("trial_uri", ""),
            source=data.get("source", "swebenchpro"),
            task_checksum=data.get("task_checksum", ""),
            mcp_enabled=mcp_enabled,
            mcp_servers=mcp_config.get("mcpServers", {}),
            environment_setup_duration=timing.get("environment_setup", 0.0),
            agent_setup_duration=timing.get("agent_setup", 0.0),
            agent_execution_duration=timing.get("agent_execution", 0.0),
            verifier_duration=timing.get("verifier", 0.0),
            agent_import_path=agent_config.get("import_path", ""),
            agent_model_name=agent_config.get("model_name", ""),
        )
    
    def _extract_task_id(self, data: dict) -> str:
        """Extract task ID from result."""
        # SWEBench format uses nested task_id
        if "task_id" in data and isinstance(data["task_id"], dict):
            task_id_obj = data["task_id"]
            # Build task ID from path
            path = task_id_obj.get("path", "")
            if path:
                # Extract instance name from path like "datasets/swebenchpro/instance_xxx"
                parts = path.split("/")
                if parts:
                    return parts[-1]
        
        # Try task_name field
        if "task_name" in data:
            return data["task_name"]
        
        # Try trial_name
        if "trial_name" in data:
            return data["trial_name"]
        
        return "unknown"
    
    def _extract_task_metadata(self, data: dict) -> HarborTaskMetadata:
        """Extract task metadata."""
        task_name = data.get("task_name", "unknown")
        trial_name = data.get("trial_name", "")
        source = data.get("source", "swebenchpro")
        
        # Parse instance ID to extract repo info
        # Format: instance_{repo}_{hash}
        category = source
        tags = []
        
        if trial_name.startswith("instance_"):
            # Extract repo name from instance ID
            parts = trial_name.split("__")
            if len(parts) >= 2:
                repo_part = parts[0].replace("instance_", "")
                tags.append(f"repo:{repo_part}")
        
        # SWE-Bench is predominantly Python repositories
        # Can infer from repo name for specific cases
        language = "python"
        if trial_name:
            trial_lower = trial_name.lower()
            if any(ts in trial_lower for ts in ["typescript", "ts-", "-ts-"]):
                language = "typescript"
            elif any(js in trial_lower for js in ["javascript", "js-", "-js-"]):
                language = "javascript"
            elif any(go in trial_lower for go in ["golang", "go-", "-go-"]):
                language = "go"
            elif any(rust in trial_lower for rust in ["rust-", "-rust-"]):
                language = "rust"

        return HarborTaskMetadata(
            task_id=self._extract_task_id(data),
            task_name=task_name,
            category=category,
            tags=tags,
            difficulty="unknown",
            language=language,
        )
    
    def _extract_timing(self, data: dict) -> dict[str, float]:
        """Extract timing information from result."""
        timing = {}
        
        def parse_duration(section: dict) -> float:
            """Calculate duration from started_at/finished_at."""
            if not section:
                return 0.0
            started = section.get("started_at")
            finished = section.get("finished_at")
            if started and finished:
                try:
                    start_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
                    end_dt = datetime.fromisoformat(finished.replace("Z", "+00:00"))
                    return (end_dt - start_dt).total_seconds()
                except Exception:
                    pass
            return 0.0
        
        timing["environment_setup"] = parse_duration(data.get("environment_setup", {}))
        timing["agent_setup"] = parse_duration(data.get("agent_setup", {}))
        timing["agent_execution"] = parse_duration(data.get("agent_execution", {}))
        timing["verifier"] = parse_duration(data.get("verifier", {}))
        
        return timing
    
    def _extract_agent_output(self, data: dict, timing: dict) -> HarborAgentOutput:
        """Extract agent execution output."""
        agent_result = data.get("agent_result", {}) or {}
        
        return HarborAgentOutput(
            exit_code=0 if data.get("exception_info") is None else 1,
            stdout=None,
            stderr=str(data.get("exception_info")) if data.get("exception_info") else None,
            duration_seconds=timing.get("agent_execution", 0.0),
            agent_type=self._extract_agent_name(data),
        )
    
    def _extract_verifier_result(
        self,
        data: dict,
        reward_raw: Optional[str],
    ) -> HarborVerifierResult:
        """Extract verifier/test result."""
        verifier_result = data.get("verifier_result", {}) or {}
        rewards = verifier_result.get("rewards", {})
        
        # Extract reward value
        reward_value = rewards.get("reward", 0.0)
        passed = float(reward_value) > 0.0
        
        # Calculate verifier duration
        verifier_timing = data.get("verifier", {})
        duration = 0.0
        if verifier_timing:
            started = verifier_timing.get("started_at")
            finished = verifier_timing.get("finished_at")
            if started and finished:
                try:
                    start_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
                    end_dt = datetime.fromisoformat(finished.replace("Z", "+00:00"))
                    duration = (end_dt - start_dt).total_seconds()
                except Exception:
                    pass
        
        return HarborVerifierResult(
            passed=passed,
            reward=rewards,
            reason=None,
            duration_seconds=duration,
            reward_raw=reward_raw,
        )
    
    def _extract_model_name(self, data: dict) -> Optional[str]:
        """Extract model name from result."""
        # Try agent_info first
        agent_info = data.get("agent_info", {})
        if agent_info:
            model_info = agent_info.get("model_info", {})
            if model_info:
                provider = model_info.get("provider", "")
                name = model_info.get("name", "")
                if provider and name:
                    return f"{provider}/{name}"
                return name or None
        
        # Try config
        config = data.get("config", {})
        agent_config = config.get("agent", {})
        if agent_config:
            return agent_config.get("model_name")
        
        return None
    
    def _extract_agent_name(self, data: dict) -> Optional[str]:
        """Extract agent name from result."""
        agent_info = data.get("agent_info", {})
        if agent_info:
            return agent_info.get("name")
        
        config = data.get("config", {})
        agent_config = config.get("agent", {})
        if agent_config:
            return agent_config.get("name")
        
        return None
