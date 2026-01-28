"""
Parse Harbor result.json files to extract metrics and task information.

Harbor result.json contains the output of a task evaluation including:
- Test pass/fail status
- Reward metrics from verifier
- Task metadata
- Agent output metadata
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from datetime import datetime


@dataclass
class HarborTaskMetadata:
    """Metadata about a Harbor task."""
    task_id: str
    task_name: str
    category: str
    tags: list[str] = field(default_factory=list)
    difficulty: str = "unknown"


@dataclass
class HarborAgentOutput:
    """Agent output information."""
    exit_code: int = 0
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    duration_seconds: float = 0.0
    agent_type: Optional[str] = None


@dataclass
class HarborVerifierResult:
    """Verifier/test result."""
    passed: bool = False
    reward: dict[str, Any] = field(default_factory=dict)
    reason: Optional[str] = None
    duration_seconds: float = 0.0
    reward_raw: Optional[str] = None  # Raw reward.txt content


@dataclass
class HarborResult:
    """Complete Harbor evaluation result."""
    task_id: str
    task_metadata: HarborTaskMetadata
    agent_output: HarborAgentOutput
    verifier_result: HarborVerifierResult
    
    # Overall status
    passed: bool = False
    duration_seconds: float = 0.0
    
    # Metadata
    evaluated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    model_name: Optional[str] = None
    agent_name: Optional[str] = None
    
    # Raw data for debugging
    raw_result: Optional[dict] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "task_id": self.task_id,
            "task_metadata": {
                "task_id": self.task_metadata.task_id,
                "task_name": self.task_metadata.task_name,
                "category": self.task_metadata.category,
                "tags": self.task_metadata.tags,
                "difficulty": self.task_metadata.difficulty,
            },
            "agent_output": {
                "exit_code": self.agent_output.exit_code,
                "stdout": self.agent_output.stdout,
                "stderr": self.agent_output.stderr,
                "duration_seconds": self.agent_output.duration_seconds,
                "agent_type": self.agent_output.agent_type,
            },
            "verifier_result": {
                "passed": self.verifier_result.passed,
                "reward": self.verifier_result.reward,
                "reason": self.verifier_result.reason,
                "duration_seconds": self.verifier_result.duration_seconds,
            },
            "passed": self.passed,
            "duration_seconds": self.duration_seconds,
            "evaluated_at": self.evaluated_at,
            "model_name": self.model_name,
            "agent_name": self.agent_name,
        }


class HarborResultParser:
    """Parse Harbor result.json files."""
    
    def parse_file(self, result_path: Path) -> HarborResult:
        """
        Parse a result.json file from Harbor.
        
        Args:
            result_path: Path to result.json
            
        Returns:
            HarborResult with extracted metrics
        """
        with open(result_path) as f:
            data = json.load(f)
        
        return self.parse_dict(data, result_path)
    
    def parse_dict(self, data: dict, source_path: Optional[Path] = None) -> HarborResult:
        """
        Parse a Harbor result dictionary.
        
        Args:
            data: Parsed result.json dictionary
            source_path: Optional path for additional context
            
        Returns:
            HarborResult with extracted metrics
        """
        task_id = self._extract_task_id(data)
        task_metadata = self._extract_task_metadata(data)
        agent_output = self._extract_agent_output(data)
        verifier_result = self._extract_verifier_result(data, source_path)
        
        # Determine overall pass/fail
        passed = verifier_result.passed and agent_output.exit_code == 0
        
        # Calculate total duration
        duration = agent_output.duration_seconds + verifier_result.duration_seconds
        
        return HarborResult(
            task_id=task_id,
            task_metadata=task_metadata,
            agent_output=agent_output,
            verifier_result=verifier_result,
            passed=passed,
            duration_seconds=duration,
            model_name=self._extract_model_name(data),
            agent_name=self._extract_agent_name(data),
            raw_result=data,
        )
    
    def _extract_task_id(self, data: dict) -> str:
        """Extract task ID from result."""
        # Try various paths where task ID might be stored
        if "task_id" in data:
            return data["task_id"]
        if "task" in data and isinstance(data["task"], dict):
            if "task_id" in data["task"]:
                return data["task"]["task_id"]
        if "metadata" in data and isinstance(data["metadata"], dict):
            if "task_id" in data["metadata"]:
                return data["metadata"]["task_id"]
        return "unknown"
    
    def _extract_task_metadata(self, data: dict) -> HarborTaskMetadata:
        """Extract task metadata."""
        metadata = data.get("metadata", {}) or {}
        if isinstance(metadata, dict):
            task = data.get("task", {}) or {}
            if isinstance(task, dict):
                # Merge task and metadata
                combined = {**task, **metadata}
            else:
                combined = metadata
        else:
            combined = {}
        
        return HarborTaskMetadata(
            task_id=combined.get("task_id", "unknown"),
            task_name=combined.get("task_name", combined.get("name", "unknown")),
            category=combined.get("category", "unknown"),
            tags=combined.get("tags", []),
            difficulty=combined.get("difficulty", "unknown"),
        )
    
    def _extract_agent_output(self, data: dict) -> HarborAgentOutput:
        """Extract agent execution output."""
        agent_data = data.get("agent", {}) or {}
        if not isinstance(agent_data, dict):
            agent_data = {}
        
        # Try to extract duration
        duration = 0.0
        if "duration" in agent_data:
            duration = float(agent_data["duration"])
        elif "duration_seconds" in agent_data:
            duration = float(agent_data["duration_seconds"])
        
        return HarborAgentOutput(
            exit_code=agent_data.get("exit_code", 0),
            stdout=agent_data.get("stdout", agent_data.get("output")),
            stderr=agent_data.get("stderr"),
            duration_seconds=duration,
            agent_type=agent_data.get("agent_type", agent_data.get("type")),
        )
    
    def _extract_verifier_result(self, data: dict, source_path: Optional[Path] = None) -> HarborVerifierResult:
        """Extract verifier/test result."""
        verifier_data = data.get("verifier", {}) or {}
        if not isinstance(verifier_data, dict):
            verifier_data = {}
        
        # Extract reward metrics
        reward = {}
        if "reward" in verifier_data and isinstance(verifier_data["reward"], dict):
            reward = verifier_data["reward"]
        
        # Try to infer pass/fail from various sources
        passed = False
        
        # Check explicit passed field
        if "passed" in verifier_data:
            passed = bool(verifier_data["passed"])
        elif "passed" in data:
            passed = bool(data["passed"])
        
        # Check reward-based metrics
        if not passed and reward:
            # If we have a "passed" reward metric, use it
            if "passed" in reward:
                passed = bool(reward["passed"])
            # Or check if there's a high primary metric
            elif "mrr" in reward and reward["mrr"] > 0:
                passed = True
            elif "success" in reward:
                passed = bool(reward["success"])
        
        # Try to extract reward from file if path is provided
        reward_raw = None
        if source_path and source_path.parent.exists():
            reward_file = source_path.parent / "logs" / "verifier" / "reward.json"
            if reward_file.exists():
                try:
                    with open(reward_file) as f:
                        file_reward = json.load(f)
                        if isinstance(file_reward, dict):
                            reward.update(file_reward)
                except Exception:
                    pass
            
            # Also try reward.txt
            reward_txt_file = source_path.parent / "logs" / "verifier" / "reward.txt"
            if reward_txt_file.exists():
                try:
                    reward_raw = reward_txt_file.read_text().strip()
                except Exception:
                    pass
        
        # Extract duration
        duration = 0.0
        if "duration" in verifier_data:
            duration = float(verifier_data["duration"])
        elif "duration_seconds" in verifier_data:
            duration = float(verifier_data["duration_seconds"])
        
        return HarborVerifierResult(
            passed=passed,
            reward=reward,
            reason=verifier_data.get("reason", verifier_data.get("error")),
            duration_seconds=duration,
            reward_raw=reward_raw,
        )
    
    def _extract_model_name(self, data: dict) -> Optional[str]:
        """Extract model name from result."""
        if "model" in data:
            return data["model"]
        if "metadata" in data and isinstance(data["metadata"], dict):
            return data["metadata"].get("model")
        return None
    
    def _extract_agent_name(self, data: dict) -> Optional[str]:
        """Extract agent name from result."""
        if "agent" in data and isinstance(data["agent"], dict):
            return data["agent"].get("name", data["agent"].get("agent_name"))
        if "metadata" in data and isinstance(data["metadata"], dict):
            return data["metadata"].get("agent")
        return None
