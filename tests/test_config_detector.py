"""Unit tests for src/ingest/config_detector.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.ingest.config_detector import (
    AgentConfig,
    AgentConfigResult,
    detect_agent_config,
    detect_agent_config_detailed,
)


@pytest.fixture()
def trial_dir(tmp_path: Path) -> Path:
    """Create a minimal trial directory structure."""
    agent_dir = tmp_path / "agent"
    agent_dir.mkdir()
    sessions_dir = agent_dir / "sessions"
    sessions_dir.mkdir()
    return tmp_path


def _write_mcp_json(trial_dir: Path, data: dict, location: str = "agent/.mcp.json") -> None:
    path = trial_dir / location
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


class TestDetectBaseline:
    """Detect BASELINE config."""

    def test_no_mcp_json_with_baseline_parent(self, tmp_path: Path) -> None:
        trial = tmp_path / "baseline" / "2026-01-28__15-21-58" / "instance_xyz"
        trial.mkdir(parents=True)
        assert detect_agent_config(trial) == AgentConfig.BASELINE

    def test_no_mcp_json_no_parent_hint(self, trial_dir: Path) -> None:
        result = detect_agent_config(trial_dir)
        assert result == AgentConfig.BASELINE

    def test_empty_servers(self, trial_dir: Path) -> None:
        _write_mcp_json(trial_dir, {"mcpServers": {}})
        assert detect_agent_config(trial_dir) == AgentConfig.BASELINE

    def test_no_servers_key(self, trial_dir: Path) -> None:
        _write_mcp_json(trial_dir, {"other": "data"})
        assert detect_agent_config(trial_dir) == AgentConfig.BASELINE


class TestDetectMCPBase:
    """Detect MCP_BASE config (sourcegraph without deepsearch)."""

    def test_sourcegraph_mcp_json(self, trial_dir: Path) -> None:
        _write_mcp_json(trial_dir, {
            "mcpServers": {
                "sourcegraph": {
                    "type": "http",
                    "url": "https://sourcegraph.sourcegraph.com/.api/mcp/v1",
                    "headers": {"Authorization": "token test"},
                }
            }
        })
        result = detect_agent_config_detailed(trial_dir)
        assert result.config == AgentConfig.MCP_BASE
        assert result.source == "mcp_json"

    def test_sourcegraph_folder_name(self, tmp_path: Path) -> None:
        trial = tmp_path / "sourcegraph" / "2026-01-28" / "instance_abc"
        trial.mkdir(parents=True)
        result = detect_agent_config_detailed(trial)
        assert result.config == AgentConfig.MCP_BASE
        assert result.source == "folder_name"

    def test_sourcegraph_hybrid_folder_name(self, tmp_path: Path) -> None:
        trial = tmp_path / "sourcegraph_hybrid" / "2026-01-28" / "instance_abc"
        trial.mkdir(parents=True)
        assert detect_agent_config(trial) == AgentConfig.MCP_BASE


class TestDetectMCPFull:
    """Detect MCP_FULL config (deepsearch)."""

    def test_deepsearch_mcp_json(self, trial_dir: Path) -> None:
        _write_mcp_json(trial_dir, {
            "mcpServers": {
                "deepsearch": {
                    "type": "http",
                    "url": "https://sourcegraph.sourcegraph.com/.api/mcp/deepsearch",
                    "headers": {"Authorization": "token test"},
                }
            }
        })
        result = detect_agent_config_detailed(trial_dir)
        assert result.config == AgentConfig.MCP_FULL
        assert result.source == "mcp_json"
        assert result.mcp_json_path is not None

    def test_deepsearch_in_url(self, trial_dir: Path) -> None:
        _write_mcp_json(trial_dir, {
            "mcpServers": {
                "custom_name": {
                    "type": "http",
                    "url": "https://example.com/.api/mcp/deepsearch",
                }
            }
        })
        assert detect_agent_config(trial_dir) == AgentConfig.MCP_FULL

    def test_deepsearch_folder_name(self, tmp_path: Path) -> None:
        trial = tmp_path / "deepsearch" / "2026-01-27" / "instance_xyz"
        trial.mkdir(parents=True)
        assert detect_agent_config(trial) == AgentConfig.MCP_FULL


class TestSessionsLocation:
    """Detect from agent/sessions/.mcp.json."""

    def test_sessions_mcp_json(self, trial_dir: Path) -> None:
        _write_mcp_json(trial_dir, {
            "mcpServers": {
                "sourcegraph": {
                    "type": "http",
                    "url": "https://sourcegraph.com/.api/mcp/v1",
                }
            }
        }, location="agent/sessions/.mcp.json")
        result = detect_agent_config_detailed(trial_dir)
        assert result.config == AgentConfig.MCP_BASE
        assert "sessions" in (result.mcp_json_path or "")

    def test_agent_mcp_json_takes_precedence(self, trial_dir: Path) -> None:
        """agent/.mcp.json is checked before agent/sessions/.mcp.json."""
        _write_mcp_json(trial_dir, {
            "mcpServers": {
                "deepsearch": {
                    "type": "http",
                    "url": "https://example.com/.api/mcp/deepsearch",
                }
            }
        }, location="agent/.mcp.json")
        _write_mcp_json(trial_dir, {
            "mcpServers": {
                "sourcegraph": {
                    "type": "http",
                    "url": "https://example.com/.api/mcp/v1",
                }
            }
        }, location="agent/sessions/.mcp.json")
        assert detect_agent_config(trial_dir) == AgentConfig.MCP_FULL


class TestEdgeCases:
    """Edge cases: malformed JSON, missing files."""

    def test_malformed_json_falls_back_to_folder(self, tmp_path: Path) -> None:
        trial = tmp_path / "deepsearch" / "timestamp" / "instance"
        (trial / "agent").mkdir(parents=True)
        mcp_path = trial / "agent" / ".mcp.json"
        mcp_path.write_text("{invalid json", encoding="utf-8")
        result = detect_agent_config_detailed(trial)
        assert result.config == AgentConfig.MCP_FULL
        assert result.source == "folder_name"

    def test_empty_mcp_json_file(self, trial_dir: Path) -> None:
        mcp_path = trial_dir / "agent" / ".mcp.json"
        mcp_path.write_text("", encoding="utf-8")
        # Empty file => JSONDecodeError => falls back to folder name
        # No folder hint => BASELINE default
        assert detect_agent_config(trial_dir) == AgentConfig.BASELINE

    def test_mcp_json_with_null_servers(self, trial_dir: Path) -> None:
        _write_mcp_json(trial_dir, {"mcpServers": None})
        assert detect_agent_config(trial_dir) == AgentConfig.BASELINE

    def test_nonexistent_directory(self, tmp_path: Path) -> None:
        trial = tmp_path / "does_not_exist"
        result = detect_agent_config(trial)
        assert result == AgentConfig.BASELINE


class TestAgentConfigEnum:
    """AgentConfig enum properties."""

    def test_string_values(self) -> None:
        assert AgentConfig.BASELINE.value == "BASELINE"
        assert AgentConfig.MCP_BASE.value == "MCP_BASE"
        assert AgentConfig.MCP_FULL.value == "MCP_FULL"

    def test_is_string_enum(self) -> None:
        assert isinstance(AgentConfig.BASELINE, str)
        assert AgentConfig.BASELINE == "BASELINE"


class TestAgentConfigResult:
    """AgentConfigResult is frozen."""

    def test_frozen(self) -> None:
        result = AgentConfigResult(
            config=AgentConfig.BASELINE,
            source="mcp_json",
            mcp_json_path="/tmp/test",
        )
        with pytest.raises(AttributeError):
            result.config = AgentConfig.MCP_FULL  # type: ignore[misc]

    def test_default_mcp_json_path(self) -> None:
        result = AgentConfigResult(config=AgentConfig.BASELINE, source="folder_name")
        assert result.mcp_json_path is None
