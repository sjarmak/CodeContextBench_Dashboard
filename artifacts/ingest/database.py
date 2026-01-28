"""
SQLite database for storing ingested metrics.

Provides a simple interface for storing and querying:
- Harbor evaluation results
- Tool usage patterns
- Agent performance metrics
- Experiment-level statistics
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .harbor_parser import HarborResult
from .transcript_parser import TranscriptMetrics


class MetricsDatabase:
    """SQLite database for metrics storage and retrieval."""
    
    def __init__(self, db_path: Path):
        """
        Initialize database connection.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_schema()
    
    def _initialize_schema(self) -> None:
        """Create tables if they don't exist."""
        with self._connect() as conn:
            cursor = conn.cursor()
            
            # Harbor results table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS harbor_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    experiment_id TEXT,
                    job_id TEXT,
                    
                    -- Task info
                    task_name TEXT,
                    task_category TEXT,
                    task_difficulty TEXT,
                    task_tags TEXT,
                    
                    -- Agent info
                    agent_name TEXT,
                    model_name TEXT,
                    
                    -- Results
                    passed BOOLEAN,
                    exit_code INTEGER,
                    
                    -- Timing
                    agent_duration_seconds REAL,
                    verifier_duration_seconds REAL,
                    total_duration_seconds REAL,
                    
                    -- Metrics
                    reward_metrics TEXT,
                    reward_primary REAL,
                    
                    -- Metadata
                    evaluated_at TEXT,
                    ingested_at TEXT,
                    
                    UNIQUE(task_id, experiment_id, job_id)
                )
            """)
            
            # Create indexes separately
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_hr_experiment ON harbor_results(experiment_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_hr_passed ON harbor_results(passed)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_hr_model ON harbor_results(model_name)")
            
            # Tool usage table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tool_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    experiment_id TEXT,
                    job_id TEXT,
                    
                    -- Tool counts
                    total_calls INTEGER,
                    mcp_calls INTEGER,
                    deep_search_calls INTEGER,
                    local_calls INTEGER,
                    other_calls INTEGER,
                    
                    -- Tool breakdown
                    tool_calls_by_name TEXT,
                    
                    -- Token usage
                    total_input_tokens INTEGER,
                    total_output_tokens INTEGER,
                    avg_tokens_per_call REAL,
                    
                    -- Success metrics
                    successful_calls INTEGER,
                    failed_calls INTEGER,
                    success_rate REAL,
                    
                    -- Efficiency
                    mcp_vs_local_ratio REAL,
                    
                    -- File access
                    unique_files_accessed INTEGER,
                    search_query_count INTEGER,
                    
                    -- Metadata
                    transcript_length INTEGER,
                    ingested_at TEXT,
                    
                    UNIQUE(task_id, experiment_id, job_id),
                    FOREIGN KEY(task_id, experiment_id, job_id) 
                        REFERENCES harbor_results(task_id, experiment_id, job_id)
                        ON DELETE CASCADE
                )
            """)
            
            # Create indexes separately
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tu_experiment ON tool_usage(experiment_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tu_mcp_calls ON tool_usage(mcp_calls)")
            
            # Experiment summary table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS experiment_summary (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    experiment_id TEXT UNIQUE NOT NULL,
                    
                    -- Task stats
                    total_tasks INTEGER,
                    completed_tasks INTEGER,
                    passed_tasks INTEGER,
                    
                    -- Agent stats
                    agent_name TEXT,
                    model_name TEXT,
                    
                    -- Performance metrics
                    pass_rate REAL,
                    avg_duration_seconds REAL,
                    
                    -- Tool metrics
                    avg_mcp_calls REAL,
                    avg_deep_search_calls REAL,
                    avg_local_calls REAL,
                    
                    -- Metadata
                    created_at TEXT,
                    updated_at TEXT
                )
            """)
            
            # Create indexes separately
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_es_experiment ON experiment_summary(experiment_id)")
            
            conn.commit()
    
    def _connect(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def store_harbor_result(
        self,
        result: HarborResult,
        experiment_id: Optional[str] = None,
        job_id: Optional[str] = None,
    ) -> None:
        """
        Store a Harbor evaluation result.
        
        Args:
            result: HarborResult to store
            experiment_id: Optional experiment ID
            job_id: Optional job ID
        """
        # Extract primary reward
        reward_primary = None
        if result.verifier_result.reward:
            # Try to find primary metric
            for metric in ["mrr", "passed", "success", "score", "reward"]:
                if metric in result.verifier_result.reward:
                    reward_primary = result.verifier_result.reward[metric]
                    break
        
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO harbor_results
                (task_id, experiment_id, job_id, task_name, task_category, task_difficulty,
                 task_tags, agent_name, model_name, passed, exit_code,
                 agent_duration_seconds, verifier_duration_seconds, total_duration_seconds,
                 reward_metrics, reward_primary, evaluated_at, ingested_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result.task_id,
                experiment_id,
                job_id,
                result.task_metadata.task_name,
                result.task_metadata.category,
                result.task_metadata.difficulty,
                json.dumps(result.task_metadata.tags),
                result.agent_name,
                result.model_name,
                result.passed,
                result.agent_output.exit_code,
                result.agent_output.duration_seconds,
                result.verifier_result.duration_seconds,
                result.duration_seconds,
                json.dumps(result.verifier_result.reward),
                reward_primary,
                result.evaluated_at,
                datetime.utcnow().isoformat(),
            ))
            conn.commit()
    
    def store_tool_usage(
        self,
        task_id: str,
        metrics: TranscriptMetrics,
        experiment_id: Optional[str] = None,
        job_id: Optional[str] = None,
    ) -> None:
        """
        Store tool usage metrics.
        
        Args:
            task_id: Task ID
            metrics: TranscriptMetrics with tool usage
            experiment_id: Optional experiment ID
            job_id: Optional job ID
        """
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO tool_usage
                (task_id, experiment_id, job_id, total_calls, mcp_calls, deep_search_calls,
                 local_calls, other_calls, tool_calls_by_name, total_input_tokens,
                 total_output_tokens, avg_tokens_per_call, successful_calls, failed_calls,
                 success_rate, mcp_vs_local_ratio, unique_files_accessed, search_query_count,
                 transcript_length, ingested_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task_id,
                experiment_id,
                job_id,
                metrics.total_tool_calls,
                metrics.mcp_calls,
                metrics.deep_search_calls,
                metrics.local_calls,
                metrics.other_calls,
                json.dumps(metrics.tool_calls_by_name),
                metrics.total_input_tokens,
                metrics.total_output_tokens,
                metrics.avg_tokens_per_call,
                metrics.successful_calls,
                metrics.failed_calls,
                metrics.success_rate,
                metrics.mcp_vs_local_ratio,
                metrics.unique_file_count,
                len(metrics.search_queries),
                metrics.transcript_length,
                datetime.utcnow().isoformat(),
            ))
            conn.commit()
    
    def get_harbor_result(
        self,
        task_id: str,
        experiment_id: Optional[str] = None,
        job_id: Optional[str] = None,
    ) -> Optional[dict]:
        """Get a stored Harbor result."""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM harbor_results
                WHERE task_id = ? AND experiment_id = ? AND job_id = ?
            """, (task_id, experiment_id, job_id))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_experiment_results(self, experiment_id: str) -> list[dict]:
        """Get all results for an experiment."""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM harbor_results
                WHERE experiment_id = ?
                ORDER BY evaluated_at DESC
            """, (experiment_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_experiment_summary(self, experiment_id: str) -> Optional[dict]:
        """Get summary statistics for an experiment."""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM experiment_summary
                WHERE experiment_id = ?
            """, (experiment_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def update_experiment_summary(self, experiment_id: str) -> None:
        """Compute and store experiment summary statistics."""
        with self._connect() as conn:
            cursor = conn.cursor()
            
            # Get results for this experiment
            cursor.execute("""
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN passed THEN 1 ELSE 0 END) as passed,
                       AVG(total_duration_seconds) as avg_duration,
                       agent_name, model_name
                FROM harbor_results
                WHERE experiment_id = ?
                GROUP BY agent_name, model_name
            """, (experiment_id,))
            
            result = cursor.fetchone()
            if not result:
                return
            
            total = result["total"] or 0
            passed = result["passed"] or 0
            pass_rate = (passed / total) if total > 0 else 0.0
            
            # Get tool metrics
            cursor.execute("""
                SELECT AVG(mcp_calls) as avg_mcp,
                       AVG(deep_search_calls) as avg_deep_search,
                       AVG(local_calls) as avg_local
                FROM tool_usage
                WHERE experiment_id = ?
            """, (experiment_id,))
            
            tool_result = cursor.fetchone()
            
            # Insert or update summary
            cursor.execute("""
                INSERT OR REPLACE INTO experiment_summary
                (experiment_id, total_tasks, passed_tasks, pass_rate,
                 agent_name, model_name, avg_duration_seconds,
                 avg_mcp_calls, avg_deep_search_calls, avg_local_calls,
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                experiment_id,
                total,
                passed,
                pass_rate,
                result["agent_name"],
                result["model_name"],
                result["avg_duration"],
                tool_result["avg_mcp"] if tool_result else 0,
                tool_result["avg_deep_search"] if tool_result else 0,
                tool_result["avg_local"] if tool_result else 0,
                datetime.utcnow().isoformat(),
                datetime.utcnow().isoformat(),
            ))
            
            conn.commit()
    
    def get_pass_rate(self, experiment_id: Optional[str] = None) -> float:
        """Get overall pass rate."""
        with self._connect() as conn:
            cursor = conn.cursor()
            if experiment_id:
                cursor.execute("""
                    SELECT SUM(CASE WHEN passed THEN 1 ELSE 0 END) as passed,
                           COUNT(*) as total
                    FROM harbor_results
                    WHERE experiment_id = ?
                """, (experiment_id,))
            else:
                cursor.execute("""
                    SELECT SUM(CASE WHEN passed THEN 1 ELSE 0 END) as passed,
                           COUNT(*) as total
                    FROM harbor_results
                """)
            
            result = cursor.fetchone()
            total = result["total"] or 0
            passed = result["passed"] or 0
            return (passed / total) if total > 0 else 0.0
    
    def get_stats(self, experiment_id: Optional[str] = None) -> dict:
        """Get comprehensive statistics."""
        stats = {}
        
        with self._connect() as conn:
            cursor = conn.cursor()
            
            # Harbor results stats
            if experiment_id:
                cursor.execute("""
                    SELECT COUNT(*) as total,
                           SUM(CASE WHEN passed THEN 1 ELSE 0 END) as passed,
                           AVG(total_duration_seconds) as avg_duration
                    FROM harbor_results
                    WHERE experiment_id = ?
                """, (experiment_id,))
            else:
                cursor.execute("""
                    SELECT COUNT(*) as total,
                           SUM(CASE WHEN passed THEN 1 ELSE 0 END) as passed,
                           AVG(total_duration_seconds) as avg_duration
                    FROM harbor_results
                """)
            
            result = cursor.fetchone()
            stats["harbor"] = {
                "total_tasks": result["total"] or 0,
                "passed_tasks": result["passed"] or 0,
                "pass_rate": (result["passed"] / result["total"]) if result["total"] else 0,
                "avg_duration_seconds": result["avg_duration"] or 0,
            }
            
            # Tool usage stats
            if experiment_id:
                cursor.execute("""
                    SELECT AVG(mcp_calls) as avg_mcp,
                           AVG(deep_search_calls) as avg_deep_search,
                           AVG(local_calls) as avg_local,
                           AVG(mcp_vs_local_ratio) as avg_ratio,
                           AVG(success_rate) as avg_success_rate
                    FROM tool_usage
                    WHERE experiment_id = ?
                """, (experiment_id,))
            else:
                cursor.execute("""
                    SELECT AVG(mcp_calls) as avg_mcp,
                           AVG(deep_search_calls) as avg_deep_search,
                           AVG(local_calls) as avg_local,
                           AVG(mcp_vs_local_ratio) as avg_ratio,
                           AVG(success_rate) as avg_success_rate
                    FROM tool_usage
                """)
            
            result = cursor.fetchone()
            stats["tool_usage"] = {
                "avg_mcp_calls": result["avg_mcp"] or 0,
                "avg_deep_search_calls": result["avg_deep_search"] or 0,
                "avg_local_calls": result["avg_local"] or 0,
                "avg_mcp_vs_local_ratio": result["avg_ratio"] or 0,
                "avg_success_rate": result["avg_success_rate"] or 0,
            }
        
        return stats
