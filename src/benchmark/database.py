"""
Database schema and models for CodeContextBench dashboard.

Uses SQLite for persistence of:
- Benchmark registry
- Evaluation runs
- Run tasks
- Agent versions
- Task profiles
"""

import sqlite3
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
import json
from contextlib import contextmanager


# Database location
DB_PATH = Path(__file__).parent.parent.parent / "data" / "codecontextbench.db"


@contextmanager
def get_db():
    """Get database connection context manager."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_database():
    """Initialize database schema."""
    with get_db() as conn:
        cursor = conn.cursor()

        # Benchmarks registry
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS benchmarks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                folder_name TEXT UNIQUE NOT NULL,
                adapter_type TEXT,
                task_count INTEGER DEFAULT 0,
                last_validated TIMESTAMP,
                validation_status TEXT,
                description TEXT,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Evaluation runs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS evaluation_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT UNIQUE NOT NULL,
                benchmark_id INTEGER NOT NULL,
                run_type TEXT NOT NULL,
                agents TEXT NOT NULL,
                task_selection TEXT,
                concurrency INTEGER DEFAULT 1,
                status TEXT NOT NULL,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                paused_at TIMESTAMP,
                config TEXT,
                logs_path TEXT,
                output_dir TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (benchmark_id) REFERENCES benchmarks(id)
            )
        """)

        # Run tasks (individual task executions within a run)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS run_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                task_name TEXT NOT NULL,
                agent_name TEXT NOT NULL,
                status TEXT NOT NULL,
                result_path TEXT,
                trajectory_path TEXT,
                reward REAL,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                error_message TEXT,
                FOREIGN KEY (run_id) REFERENCES evaluation_runs(run_id)
            )
        """)

        # Agent versions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                model TEXT NOT NULL,
                import_path TEXT NOT NULL,
                prompt_template TEXT,
                tools_config TEXT,
                mcp_config TEXT,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 1
            )
        """)

        # Task profiles
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS task_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                benchmark_id INTEGER NOT NULL,
                task_list TEXT NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (benchmark_id) REFERENCES benchmarks(id)
            )
        """)

        # Judge evaluations
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS judge_evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                task_name TEXT NOT NULL,
                agent_name TEXT NOT NULL,
                judge_model TEXT NOT NULL,
                score REAL,
                reasoning TEXT,
                evaluation_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (run_id) REFERENCES evaluation_runs(run_id),
                UNIQUE(run_id, task_name, agent_name, judge_model)
            )
        """)

        # Evaluation reports
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS evaluation_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                task_name TEXT,
                report_type TEXT NOT NULL,
                report_data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (run_id) REFERENCES evaluation_runs(run_id)
            )
        """)

        # Indexes for performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_runs_status ON evaluation_runs(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_run_tasks_run_id ON run_tasks(run_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_run_tasks_status ON run_tasks(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_agents_active ON agent_versions(is_active)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_judge_run_id ON judge_evaluations(run_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_judge_task ON judge_evaluations(run_id, task_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_reports_run_id ON evaluation_reports(run_id)")

        conn.commit()


class BenchmarkRegistry:
    """Manage benchmark registry."""

    @staticmethod
    def add(name: str, folder_name: str, adapter_type: Optional[str] = None,
            description: Optional[str] = None, metadata: Optional[Dict] = None) -> int:
        """Add a benchmark to registry."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO benchmarks (name, folder_name, adapter_type, description, metadata)
                VALUES (?, ?, ?, ?, ?)
            """, (name, folder_name, adapter_type, description,
                  json.dumps(metadata) if metadata else None))
            return cursor.lastrowid

    @staticmethod
    def get(benchmark_id: int) -> Optional[Dict]:
        """Get benchmark by ID."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM benchmarks WHERE id = ?", (benchmark_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_by_name(name: str) -> Optional[Dict]:
        """Get benchmark by name."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM benchmarks WHERE name = ?", (name,))
            row = cursor.fetchone()
            return dict(row) if row else None

    @staticmethod
    def list_all() -> List[Dict]:
        """List all benchmarks."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM benchmarks ORDER BY name")
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def update(benchmark_id: int, **kwargs):
        """Update benchmark fields."""
        valid_fields = {'adapter_type', 'task_count', 'last_validated',
                       'validation_status', 'description', 'metadata'}
        updates = {k: v for k, v in kwargs.items() if k in valid_fields}

        if 'metadata' in updates and isinstance(updates['metadata'], dict):
            updates['metadata'] = json.dumps(updates['metadata'])

        updates['updated_at'] = datetime.utcnow().isoformat()

        if not updates:
            return

        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [benchmark_id]

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE benchmarks SET {set_clause} WHERE id = ?", values)

    @staticmethod
    def delete(benchmark_id: int):
        """Delete benchmark."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM benchmarks WHERE id = ?", (benchmark_id,))


class RunManager:
    """Manage evaluation runs."""

    @staticmethod
    def create(run_id: str, benchmark_id: int, run_type: str, agents: List[str],
               task_selection: Optional[List[str]] = None, concurrency: int = 1,
               config: Optional[Dict] = None, output_dir: Optional[str] = None) -> int:
        """Create new evaluation run."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO evaluation_runs
                (run_id, benchmark_id, run_type, agents, task_selection, concurrency,
                 status, config, output_dir)
                VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)
            """, (run_id, benchmark_id, run_type, json.dumps(agents),
                  json.dumps(task_selection) if task_selection else None,
                  concurrency, json.dumps(config) if config else None, output_dir))
            return cursor.lastrowid

    @staticmethod
    def get(run_id: str) -> Optional[Dict]:
        """Get run by ID."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM evaluation_runs WHERE run_id = ?", (run_id,))
            row = cursor.fetchone()
            if row:
                result = dict(row)
                # Parse JSON fields
                for field in ['agents', 'task_selection', 'config']:
                    if result.get(field):
                        result[field] = json.loads(result[field])
                return result
            return None

    @staticmethod
    def list_all(status: Optional[str] = None) -> List[Dict]:
        """List all runs, optionally filtered by status."""
        with get_db() as conn:
            cursor = conn.cursor()
            if status:
                cursor.execute("SELECT * FROM evaluation_runs WHERE status = ? ORDER BY created_at DESC",
                             (status,))
            else:
                cursor.execute("SELECT * FROM evaluation_runs ORDER BY created_at DESC")

            results = []
            for row in cursor.fetchall():
                result = dict(row)
                for field in ['agents', 'task_selection', 'config']:
                    if result.get(field):
                        result[field] = json.loads(result[field])
                results.append(result)
            return results

    @staticmethod
    def update_status(run_id: str, status: str, **kwargs):
        """Update run status and optional fields."""
        updates = {'status': status}
        updates.update(kwargs)

        if status == 'running' and 'started_at' not in updates:
            updates['started_at'] = datetime.utcnow().isoformat()
        elif status == 'completed' and 'completed_at' not in updates:
            updates['completed_at'] = datetime.utcnow().isoformat()
        elif status == 'paused' and 'paused_at' not in updates:
            updates['paused_at'] = datetime.utcnow().isoformat()

        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [run_id]

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE evaluation_runs SET {set_clause} WHERE run_id = ?", values)


class TaskManager:
    """Manage individual task executions."""

    @staticmethod
    def create(run_id: str, task_name: str, agent_name: str) -> int:
        """Create task record."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO run_tasks (run_id, task_name, agent_name, status)
                VALUES (?, ?, ?, 'pending')
            """, (run_id, task_name, agent_name))
            return cursor.lastrowid

    @staticmethod
    def update_status(run_id: str, task_name: str, agent_name: str, status: str, **kwargs):
        """Update task status."""
        updates = {'status': status}
        updates.update(kwargs)

        if status == 'running' and 'started_at' not in updates:
            updates['started_at'] = datetime.utcnow().isoformat()
        elif status in ('completed', 'failed') and 'completed_at' not in updates:
            updates['completed_at'] = datetime.utcnow().isoformat()

        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [run_id, task_name, agent_name]

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                UPDATE run_tasks SET {set_clause}
                WHERE run_id = ? AND task_name = ? AND agent_name = ?
            """, values)

    @staticmethod
    def get_tasks(run_id: str) -> List[Dict]:
        """Get all tasks for a run."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM run_tasks WHERE run_id = ? ORDER BY id", (run_id,))
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def get_pending_tasks(run_id: str) -> List[Dict]:
        """Get pending tasks for a run."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM run_tasks
                WHERE run_id = ? AND status = 'pending'
                ORDER BY id
            """, (run_id,))
            return [dict(row) for row in cursor.fetchall()]


class AgentRegistry:
    """Manage agent versions."""

    @staticmethod
    def add(version_id: str, name: str, model: str, import_path: str,
            description: Optional[str] = None, prompt_template: Optional[str] = None,
            tools_config: Optional[Dict] = None, mcp_config: Optional[Dict] = None,
            metadata: Optional[Dict] = None) -> int:
        """Add agent version."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO agent_versions
                (version_id, name, description, model, import_path, prompt_template,
                 tools_config, mcp_config, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (version_id, name, description, model, import_path, prompt_template,
                  json.dumps(tools_config) if tools_config else None,
                  json.dumps(mcp_config) if mcp_config else None,
                  json.dumps(metadata) if metadata else None))
            return cursor.lastrowid

    @staticmethod
    def list_all(active_only: bool = False) -> List[Dict]:
        """List all agent versions."""
        with get_db() as conn:
            cursor = conn.cursor()
            if active_only:
                cursor.execute("SELECT * FROM agent_versions WHERE is_active = 1 ORDER BY created_at DESC")
            else:
                cursor.execute("SELECT * FROM agent_versions ORDER BY created_at DESC")

            results = []
            for row in cursor.fetchall():
                result = dict(row)
                for field in ['tools_config', 'mcp_config', 'metadata']:
                    if result.get(field):
                        result[field] = json.loads(result[field])
                results.append(result)
            return results

    @staticmethod
    def get(version_id: str) -> Optional[Dict]:
        """Get agent version."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM agent_versions WHERE version_id = ?", (version_id,))
            row = cursor.fetchone()
            if row:
                result = dict(row)
                for field in ['tools_config', 'mcp_config', 'metadata']:
                    if result.get(field):
                        result[field] = json.loads(result[field])
                return result
            return None

    @staticmethod
    def deactivate(version_id: str):
        """Deactivate agent version."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE agent_versions SET is_active = 0 WHERE version_id = ?",
                         (version_id,))


class TaskProfileManager:
    """Manage task profiles."""

    @staticmethod
    def add(profile_id: str, name: str, benchmark_id: int, task_list: List[str],
            description: Optional[str] = None) -> int:
        """Add task profile."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO task_profiles (profile_id, name, benchmark_id, task_list, description)
                VALUES (?, ?, ?, ?, ?)
            """, (profile_id, name, benchmark_id, json.dumps(task_list), description))
            return cursor.lastrowid

    @staticmethod
    def list_for_benchmark(benchmark_id: int) -> List[Dict]:
        """List profiles for a benchmark."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM task_profiles
                WHERE benchmark_id = ?
                ORDER BY name
            """, (benchmark_id,))

            results = []
            for row in cursor.fetchall():
                result = dict(row)
                if result.get('task_list'):
                    result['task_list'] = json.loads(result['task_list'])
                results.append(result)
            return results

    @staticmethod
    def get(profile_id: str) -> Optional[Dict]:
        """Get task profile."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM task_profiles WHERE profile_id = ?", (profile_id,))
            row = cursor.fetchone()
            if row:
                result = dict(row)
                if result.get('task_list'):
                    result['task_list'] = json.loads(result['task_list'])
                return result
            return None


class JudgeEvaluationRegistry:
    """Manage LLM judge evaluations."""

    @staticmethod
    def add(run_id: str, task_name: str, agent_name: str, judge_model: str,
            score: Optional[float] = None, reasoning: Optional[str] = None,
            evaluation_data: Optional[Dict] = None) -> int:
        """Add or update judge evaluation for a task."""
        with get_db() as conn:
            cursor = conn.cursor()

            # Try to update existing first
            cursor.execute("""
                UPDATE judge_evaluations
                SET score = ?, reasoning = ?, evaluation_data = ?, created_at = CURRENT_TIMESTAMP
                WHERE run_id = ? AND task_name = ? AND agent_name = ? AND judge_model = ?
            """, (score, reasoning,
                  json.dumps(evaluation_data) if evaluation_data else None,
                  run_id, task_name, agent_name, judge_model))

            if cursor.rowcount == 0:
                # Insert new
                cursor.execute("""
                    INSERT INTO judge_evaluations
                    (run_id, task_name, agent_name, judge_model, score, reasoning, evaluation_data)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (run_id, task_name, agent_name, judge_model, score, reasoning,
                      json.dumps(evaluation_data) if evaluation_data else None))
                return cursor.lastrowid

            return cursor.lastrowid

    @staticmethod
    def get(run_id: str, task_name: str, agent_name: str, judge_model: str) -> Optional[Dict]:
        """Get judge evaluation for a specific task."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM judge_evaluations
                WHERE run_id = ? AND task_name = ? AND agent_name = ? AND judge_model = ?
            """, (run_id, task_name, agent_name, judge_model))

            row = cursor.fetchone()
            if row:
                result = dict(row)
                if result.get('evaluation_data'):
                    result['evaluation_data'] = json.loads(result['evaluation_data'])
                return result
            return None

    @staticmethod
    def list_for_run(run_id: str) -> List[Dict]:
        """List all judge evaluations for a run."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM judge_evaluations
                WHERE run_id = ?
                ORDER BY task_name, agent_name
            """, (run_id,))

            results = []
            for row in cursor.fetchall():
                result = dict(row)
                if result.get('evaluation_data'):
                    result['evaluation_data'] = json.loads(result['evaluation_data'])
                results.append(result)
            return results

    @staticmethod
    def list_for_task(run_id: str, task_name: str) -> List[Dict]:
        """List all judge evaluations for a specific task."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM judge_evaluations
                WHERE run_id = ? AND task_name = ?
                ORDER BY agent_name, judge_model
            """, (run_id, task_name))

            results = []
            for row in cursor.fetchall():
                result = dict(row)
                if result.get('evaluation_data'):
                    result['evaluation_data'] = json.loads(result['evaluation_data'])
                results.append(result)
            return results


class EvaluationReportRegistry:
    """Manage evaluation reports."""

    @staticmethod
    def add(run_id: str, report_type: str, report_data: Dict,
            task_name: Optional[str] = None) -> int:
        """Add evaluation report."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO evaluation_reports (run_id, task_name, report_type, report_data)
                VALUES (?, ?, ?, ?)
            """, (run_id, task_name, report_type, json.dumps(report_data)))
            return cursor.lastrowid

    @staticmethod
    def get_latest(run_id: str, task_name: Optional[str] = None,
                   report_type: Optional[str] = None) -> Optional[Dict]:
        """Get latest report for a run/task."""
        with get_db() as conn:
            cursor = conn.cursor()

            if task_name and report_type:
                query = """
                    SELECT * FROM evaluation_reports
                    WHERE run_id = ? AND task_name = ? AND report_type = ?
                    ORDER BY created_at DESC LIMIT 1
                """
                params = (run_id, task_name, report_type)
            elif task_name:
                query = """
                    SELECT * FROM evaluation_reports
                    WHERE run_id = ? AND task_name = ?
                    ORDER BY created_at DESC LIMIT 1
                """
                params = (run_id, task_name)
            elif report_type:
                query = """
                    SELECT * FROM evaluation_reports
                    WHERE run_id = ? AND report_type = ?
                    ORDER BY created_at DESC LIMIT 1
                """
                params = (run_id, report_type)
            else:
                query = """
                    SELECT * FROM evaluation_reports
                    WHERE run_id = ?
                    ORDER BY created_at DESC LIMIT 1
                """
                params = (run_id,)

            cursor.execute(query, params)
            row = cursor.fetchone()

            if row:
                result = dict(row)
                if result.get('report_data'):
                    result['report_data'] = json.loads(result['report_data'])
                return result
            return None

    @staticmethod
    def list_for_run(run_id: str, task_name: Optional[str] = None) -> List[Dict]:
        """List all reports for a run."""
        with get_db() as conn:
            cursor = conn.cursor()

            if task_name:
                cursor.execute("""
                    SELECT * FROM evaluation_reports
                    WHERE run_id = ? AND task_name = ?
                    ORDER BY created_at DESC
                """, (run_id, task_name))
            else:
                cursor.execute("""
                    SELECT * FROM evaluation_reports
                    WHERE run_id = ?
                    ORDER BY created_at DESC
                """, (run_id,))

            results = []
            for row in cursor.fetchall():
                result = dict(row)
                if result.get('report_data'):
                    result['report_data'] = json.loads(result['report_data'])
                results.append(result)
            return results


# Initialize database on import
init_database()
