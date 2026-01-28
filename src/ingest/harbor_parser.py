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
    language: str = "unknown"


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
                "language": self.task_metadata.language,
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
        # Harbor format uses task_name at top level
        if "task_name" in data:
            return data["task_name"]
        # Try various paths where task ID might be stored
        if "task_id" in data:
            task_id = data["task_id"]
            # Harbor format: task_id is a dict with "path" key
            if isinstance(task_id, dict) and "path" in task_id:
                # Extract task name from path
                path = task_id["path"]
                return Path(path).name if path else "unknown"
            elif isinstance(task_id, str):
                return task_id
        if "task" in data and isinstance(data["task"], dict):
            if "task_id" in data["task"]:
                return data["task"]["task_id"]
        if "metadata" in data and isinstance(data["metadata"], dict):
            if "task_id" in data["metadata"]:
                return data["metadata"]["task_id"]
        return "unknown"
    
    def _extract_task_metadata(self, data: dict) -> HarborTaskMetadata:
        """Extract task metadata."""
        # Harbor format has task_name at top level
        task_name = data.get("task_name", "unknown")
        task_id = task_name  # Use task_name as task_id

        # Extract from task_id dict if present
        task_id_data = data.get("task_id", {})
        if isinstance(task_id_data, dict) and "path" in task_id_data:
            task_path = task_id_data["path"]
            if task_id == "unknown" and task_path:
                task_id = Path(task_path).name
                task_name = task_id

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

        # Extract language from various possible sources
        language = combined.get("language", combined.get("primary_language", "unknown"))

        # Try to infer language from task_id pattern (e.g., python_web_medium_001)
        if language == "unknown" and task_id:
            language = self._infer_language_from_task_id(task_id)

        return HarborTaskMetadata(
            task_id=task_id,
            task_name=task_name if task_name != "unknown" else combined.get("task_name", combined.get("name", "unknown")),
            category=combined.get("category", "unknown"),
            tags=combined.get("tags", []),
            difficulty=combined.get("difficulty", "unknown"),
            language=language,
        )
    
    def _extract_agent_output(self, data: dict) -> HarborAgentOutput:
        """Extract agent execution output."""
        agent_data = data.get("agent", {}) or {}
        if not isinstance(agent_data, dict):
            agent_data = {}

        # Harbor format: agent_result contains token counts
        agent_result = data.get("agent_result", {}) or {}
        if not isinstance(agent_result, dict):
            agent_result = {}

        # Try to extract duration from Harbor format timing
        duration = 0.0

        # Harbor format: agent_execution has started_at/finished_at
        agent_execution = data.get("agent_execution", {})
        if isinstance(agent_execution, dict):
            started = agent_execution.get("started_at", "")
            finished = agent_execution.get("finished_at", "")
            if started and finished:
                try:
                    from datetime import datetime
                    start_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
                    end_dt = datetime.fromisoformat(finished.replace("Z", "+00:00"))
                    duration = (end_dt - start_dt).total_seconds()
                except (ValueError, TypeError):
                    pass

        # Fallback to legacy format
        if duration == 0.0:
            if "duration" in agent_data:
                duration = float(agent_data["duration"])
            elif "duration_seconds" in agent_data:
                duration = float(agent_data["duration_seconds"])

        # Extract agent type from agent_info or config
        agent_type = None
        agent_info = data.get("agent_info", {})
        if isinstance(agent_info, dict):
            agent_type = agent_info.get("name")
        if not agent_type:
            config = data.get("config", {})
            if isinstance(config, dict):
                agent_config = config.get("agent", {})
                if isinstance(agent_config, dict):
                    agent_type = agent_config.get("import_path", "").split(":")[-1] if agent_config.get("import_path") else None

        return HarborAgentOutput(
            exit_code=agent_data.get("exit_code", 0),
            stdout=agent_data.get("stdout", agent_data.get("output")),
            stderr=agent_data.get("stderr"),
            duration_seconds=duration,
            agent_type=agent_type or agent_data.get("agent_type", agent_data.get("type")),
        )
    
    def _extract_verifier_result(self, data: dict, source_path: Optional[Path] = None) -> HarborVerifierResult:
        """Extract verifier/test result."""
        # Harbor format: verifier_result at top level
        verifier_result_data = data.get("verifier_result", {}) or {}
        if not isinstance(verifier_result_data, dict):
            verifier_result_data = {}

        # Legacy format: verifier at top level
        verifier_data = data.get("verifier", {}) or {}
        if not isinstance(verifier_data, dict):
            verifier_data = {}

        # Extract reward metrics - Harbor format uses verifier_result.rewards
        reward = {}
        if "rewards" in verifier_result_data and isinstance(verifier_result_data["rewards"], dict):
            reward = verifier_result_data["rewards"]
        elif "reward" in verifier_data and isinstance(verifier_data["reward"], dict):
            reward = verifier_data["reward"]

        # Try to infer pass/fail from various sources
        passed = False

        # Harbor format: check if reward > 0
        if reward.get("reward") is not None:
            passed = float(reward["reward"]) > 0

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
        
        # Extract duration - Harbor format has verifier timing at top level
        duration = 0.0
        verifier_timing = data.get("verifier", {})
        if isinstance(verifier_timing, dict):
            started = verifier_timing.get("started_at", "")
            finished = verifier_timing.get("finished_at", "")
            if started and finished:
                try:
                    from datetime import datetime
                    start_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
                    end_dt = datetime.fromisoformat(finished.replace("Z", "+00:00"))
                    duration = (end_dt - start_dt).total_seconds()
                except (ValueError, TypeError):
                    pass

        # Fallback to legacy format
        if duration == 0.0:
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
        # Harbor format: agent_info.model_info.name
        agent_info = data.get("agent_info", {})
        if isinstance(agent_info, dict):
            model_info = agent_info.get("model_info", {})
            if isinstance(model_info, dict) and model_info.get("name"):
                return model_info["name"]

        # Also try config.agent.model_name
        config = data.get("config", {})
        if isinstance(config, dict):
            agent_config = config.get("agent", {})
            if isinstance(agent_config, dict) and agent_config.get("model_name"):
                return agent_config["model_name"]

        # Legacy paths
        if "model" in data:
            return data["model"]
        if "metadata" in data and isinstance(data["metadata"], dict):
            return data["metadata"].get("model")
        return None

    def _extract_agent_name(self, data: dict) -> Optional[str]:
        """Extract agent name from result."""
        # Harbor format: agent_info.name
        agent_info = data.get("agent_info", {})
        if isinstance(agent_info, dict) and agent_info.get("name"):
            return agent_info["name"]

        # Also try config.agent.import_path to derive agent name
        config = data.get("config", {})
        if isinstance(config, dict):
            agent_config = config.get("agent", {})
            if isinstance(agent_config, dict) and agent_config.get("import_path"):
                # Extract agent class name from import path
                import_path = agent_config["import_path"]
                if ":" in import_path:
                    return import_path.split(":")[-1]

        # Legacy paths
        if "agent" in data and isinstance(data["agent"], dict):
            return data["agent"].get("name", data["agent"].get("agent_name"))
        if "metadata" in data and isinstance(data["metadata"], dict):
            return data["metadata"].get("agent")
        return None

    def _infer_language_from_task_id(self, task_id: str) -> str:
        """
        Infer programming language from task ID patterns.

        Supports patterns like:
        - LoCoBench: {language}_{domain}_{complexity}_{num}_{category}_{difficulty}_{variant}
        - SWE-Bench: typically Python projects
        - General: language prefix patterns

        Args:
            task_id: Task identifier string

        Returns:
            Inferred language or "unknown"
        """
        if not task_id:
            return "unknown"

        task_lower = task_id.lower()

        # Known language prefixes (LoCoBench pattern)
        known_languages = [
            "python", "typescript", "javascript", "go", "rust",
            "cpp", "c", "java", "csharp", "ruby", "php", "swift",
            "kotlin", "scala", "haskell", "elixir", "clojure",
        ]

        # Check if task_id starts with a known language
        for lang in known_languages:
            if task_lower.startswith(f"{lang}_") or task_lower.startswith(f"{lang}-"):
                return lang

        # Check for language anywhere in task_id with underscore boundaries
        parts = task_lower.replace("-", "_").split("_")
        for part in parts:
            if part in known_languages:
                return part

        # SWE-Bench pattern detection (e.g., django__django-12345)
        swebench_python_repos = [
            "django", "flask", "requests", "pytest", "numpy", "pandas",
            "scikit-learn", "matplotlib", "sphinx", "sympy", "astropy",
            "pylint", "pydicom", "mwaskom", "psf", "python",
            "openlibrary", "internetarchive",
        ]
        for repo in swebench_python_repos:
            if repo in task_lower:
                return "python"

        # TypeScript repos
        swebench_typescript_repos = [
            "protonmail", "webclients",
        ]
        for repo in swebench_typescript_repos:
            if repo in task_lower:
                return "typescript"

        return "unknown"
