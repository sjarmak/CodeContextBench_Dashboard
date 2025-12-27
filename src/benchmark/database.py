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

        # Reference bundles (excerpt packs for grounded evaluation)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ref_bundles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bundle_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                sources TEXT,
                excerpts TEXT,
                excerpt_count INTEGER DEFAULT 0,
                source_hash TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Versioned checklists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS checklists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                checklist_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                ref_bundle_id TEXT,
                yaml_content TEXT NOT NULL,
                item_count INTEGER DEFAULT 0,
                categories TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (ref_bundle_id) REFERENCES ref_bundles(bundle_id)
            )
        """)

        # Checklist evaluations per task
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS checklist_evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                task_name TEXT NOT NULL,
                agent_name TEXT NOT NULL,
                checklist_id TEXT NOT NULL,
                covered_items TEXT,
                coverage_score REAL,
                accuracy_score REAL,
                contradiction_count INTEGER DEFAULT 0,
                weighted_score REAL,
                evaluation_details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (run_id) REFERENCES evaluation_runs(run_id),
                FOREIGN KEY (checklist_id) REFERENCES checklists(checklist_id),
                UNIQUE(run_id, task_name, agent_name, checklist_id)
            )
        """)

        # Grounding anchor validations
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS grounding_validations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                task_name TEXT NOT NULL,
                agent_name TEXT NOT NULL,
                anchors_total INTEGER DEFAULT 0,
                anchors_valid INTEGER DEFAULT 0,
                anchors_invalid INTEGER DEFAULT 0,
                required_areas TEXT,
                missing_areas TEXT,
                valid_anchors TEXT,
                invalid_anchors TEXT,
                grounding_score REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (run_id) REFERENCES evaluation_runs(run_id),
                UNIQUE(run_id, task_name, agent_name)
            )
        """)

        # Tool stacks for A/B comparison
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tool_stacks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stack_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                tools_enabled TEXT,
                mcp_config TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_checklist_eval_run ON checklist_evaluations(run_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_grounding_run ON grounding_validations(run_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tool_stacks_active ON tool_stacks(is_active)")

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


class RefBundleRegistry:
    """Manage reference excerpt bundles for grounded evaluation."""

    @staticmethod
    def add(bundle_id: str, name: str, sources: List[Dict], excerpts: List[Dict],
            description: Optional[str] = None, source_hash: Optional[str] = None) -> int:
        """Add a reference bundle."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO ref_bundles
                (bundle_id, name, description, sources, excerpts, excerpt_count, source_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (bundle_id, name, description,
                  json.dumps(sources), json.dumps(excerpts),
                  len(excerpts), source_hash))
            return cursor.lastrowid

    @staticmethod
    def get(bundle_id: str) -> Optional[Dict]:
        """Get reference bundle by ID."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM ref_bundles WHERE bundle_id = ?", (bundle_id,))
            row = cursor.fetchone()
            if row:
                result = dict(row)
                for field in ['sources', 'excerpts']:
                    if result.get(field):
                        result[field] = json.loads(result[field])
                return result
            return None

    @staticmethod
    def list_all() -> List[Dict]:
        """List all reference bundles."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM ref_bundles ORDER BY created_at DESC")
            results = []
            for row in cursor.fetchall():
                result = dict(row)
                for field in ['sources', 'excerpts']:
                    if result.get(field):
                        result[field] = json.loads(result[field])
                results.append(result)
            return results

    @staticmethod
    def update(bundle_id: str, **kwargs):
        """Update reference bundle."""
        valid_fields = {'name', 'description', 'sources', 'excerpts', 'source_hash'}
        updates = {k: v for k, v in kwargs.items() if k in valid_fields}

        for field in ['sources', 'excerpts']:
            if field in updates and isinstance(updates[field], (list, dict)):
                updates[field] = json.dumps(updates[field])

        if 'excerpts' in updates:
            excerpts = kwargs.get('excerpts', [])
            updates['excerpt_count'] = len(excerpts) if isinstance(excerpts, list) else 0

        updates['updated_at'] = datetime.utcnow().isoformat()

        if not updates:
            return

        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [bundle_id]

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE ref_bundles SET {set_clause} WHERE bundle_id = ?", values)


class ChecklistRegistry:
    """Manage versioned checklists."""

    @staticmethod
    def add(checklist_id: str, name: str, yaml_content: str,
            ref_bundle_id: Optional[str] = None, description: Optional[str] = None,
            categories: Optional[List[str]] = None, item_count: int = 0) -> int:
        """Add a checklist."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO checklists
                (checklist_id, name, description, ref_bundle_id, yaml_content, item_count, categories)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (checklist_id, name, description, ref_bundle_id, yaml_content,
                  item_count, json.dumps(categories) if categories else None))
            return cursor.lastrowid

    @staticmethod
    def get(checklist_id: str) -> Optional[Dict]:
        """Get checklist by ID."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM checklists WHERE checklist_id = ?", (checklist_id,))
            row = cursor.fetchone()
            if row:
                result = dict(row)
                if result.get('categories'):
                    result['categories'] = json.loads(result['categories'])
                return result
            return None

    @staticmethod
    def list_all() -> List[Dict]:
        """List all checklists."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM checklists ORDER BY created_at DESC")
            results = []
            for row in cursor.fetchall():
                result = dict(row)
                if result.get('categories'):
                    result['categories'] = json.loads(result['categories'])
                results.append(result)
            return results

    @staticmethod
    def list_for_bundle(ref_bundle_id: str) -> List[Dict]:
        """List checklists for a reference bundle."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM checklists WHERE ref_bundle_id = ?
                ORDER BY created_at DESC
            """, (ref_bundle_id,))
            results = []
            for row in cursor.fetchall():
                result = dict(row)
                if result.get('categories'):
                    result['categories'] = json.loads(result['categories'])
                results.append(result)
            return results


class ChecklistEvaluationRegistry:
    """Manage checklist evaluations per task."""

    @staticmethod
    def add(run_id: str, task_name: str, agent_name: str, checklist_id: str,
            covered_items: Optional[List[Dict]] = None,
            coverage_score: Optional[float] = None,
            accuracy_score: Optional[float] = None,
            contradiction_count: int = 0,
            weighted_score: Optional[float] = None,
            evaluation_details: Optional[Dict] = None) -> int:
        """Add or update checklist evaluation."""
        with get_db() as conn:
            cursor = conn.cursor()

            # Try to update existing
            cursor.execute("""
                UPDATE checklist_evaluations
                SET covered_items = ?, coverage_score = ?, accuracy_score = ?,
                    contradiction_count = ?, weighted_score = ?, evaluation_details = ?,
                    created_at = CURRENT_TIMESTAMP
                WHERE run_id = ? AND task_name = ? AND agent_name = ? AND checklist_id = ?
            """, (json.dumps(covered_items) if covered_items else None,
                  coverage_score, accuracy_score, contradiction_count, weighted_score,
                  json.dumps(evaluation_details) if evaluation_details else None,
                  run_id, task_name, agent_name, checklist_id))

            if cursor.rowcount == 0:
                cursor.execute("""
                    INSERT INTO checklist_evaluations
                    (run_id, task_name, agent_name, checklist_id, covered_items,
                     coverage_score, accuracy_score, contradiction_count, weighted_score,
                     evaluation_details)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (run_id, task_name, agent_name, checklist_id,
                      json.dumps(covered_items) if covered_items else None,
                      coverage_score, accuracy_score, contradiction_count, weighted_score,
                      json.dumps(evaluation_details) if evaluation_details else None))
                return cursor.lastrowid
            return cursor.lastrowid

    @staticmethod
    def get(run_id: str, task_name: str, agent_name: str,
            checklist_id: str) -> Optional[Dict]:
        """Get checklist evaluation."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM checklist_evaluations
                WHERE run_id = ? AND task_name = ? AND agent_name = ? AND checklist_id = ?
            """, (run_id, task_name, agent_name, checklist_id))
            row = cursor.fetchone()
            if row:
                result = dict(row)
                for field in ['covered_items', 'evaluation_details']:
                    if result.get(field):
                        result[field] = json.loads(result[field])
                return result
            return None

    @staticmethod
    def list_for_run(run_id: str) -> List[Dict]:
        """List all checklist evaluations for a run."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM checklist_evaluations
                WHERE run_id = ?
                ORDER BY task_name, agent_name
            """, (run_id,))
            results = []
            for row in cursor.fetchall():
                result = dict(row)
                for field in ['covered_items', 'evaluation_details']:
                    if result.get(field):
                        result[field] = json.loads(result[field])
                results.append(result)
            return results


class GroundingValidationRegistry:
    """Manage grounding anchor validations."""

    @staticmethod
    def add(run_id: str, task_name: str, agent_name: str,
            anchors_total: int = 0, anchors_valid: int = 0, anchors_invalid: int = 0,
            required_areas: Optional[List[str]] = None,
            missing_areas: Optional[List[str]] = None,
            valid_anchors: Optional[List[Dict]] = None,
            invalid_anchors: Optional[List[Dict]] = None,
            grounding_score: Optional[float] = None) -> int:
        """Add or update grounding validation."""
        with get_db() as conn:
            cursor = conn.cursor()

            # Try to update existing
            cursor.execute("""
                UPDATE grounding_validations
                SET anchors_total = ?, anchors_valid = ?, anchors_invalid = ?,
                    required_areas = ?, missing_areas = ?, valid_anchors = ?,
                    invalid_anchors = ?, grounding_score = ?,
                    created_at = CURRENT_TIMESTAMP
                WHERE run_id = ? AND task_name = ? AND agent_name = ?
            """, (anchors_total, anchors_valid, anchors_invalid,
                  json.dumps(required_areas) if required_areas else None,
                  json.dumps(missing_areas) if missing_areas else None,
                  json.dumps(valid_anchors) if valid_anchors else None,
                  json.dumps(invalid_anchors) if invalid_anchors else None,
                  grounding_score, run_id, task_name, agent_name))

            if cursor.rowcount == 0:
                cursor.execute("""
                    INSERT INTO grounding_validations
                    (run_id, task_name, agent_name, anchors_total, anchors_valid,
                     anchors_invalid, required_areas, missing_areas, valid_anchors,
                     invalid_anchors, grounding_score)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (run_id, task_name, agent_name, anchors_total, anchors_valid,
                      anchors_invalid,
                      json.dumps(required_areas) if required_areas else None,
                      json.dumps(missing_areas) if missing_areas else None,
                      json.dumps(valid_anchors) if valid_anchors else None,
                      json.dumps(invalid_anchors) if invalid_anchors else None,
                      grounding_score))
                return cursor.lastrowid
            return cursor.lastrowid

    @staticmethod
    def get(run_id: str, task_name: str, agent_name: str) -> Optional[Dict]:
        """Get grounding validation."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM grounding_validations
                WHERE run_id = ? AND task_name = ? AND agent_name = ?
            """, (run_id, task_name, agent_name))
            row = cursor.fetchone()
            if row:
                result = dict(row)
                for field in ['required_areas', 'missing_areas', 'valid_anchors', 'invalid_anchors']:
                    if result.get(field):
                        result[field] = json.loads(result[field])
                return result
            return None

    @staticmethod
    def list_for_run(run_id: str) -> List[Dict]:
        """List all grounding validations for a run."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM grounding_validations
                WHERE run_id = ?
                ORDER BY task_name, agent_name
            """, (run_id,))
            results = []
            for row in cursor.fetchall():
                result = dict(row)
                for field in ['required_areas', 'missing_areas', 'valid_anchors', 'invalid_anchors']:
                    if result.get(field):
                        result[field] = json.loads(result[field])
                results.append(result)
            return results


class ToolStackRegistry:
    """Manage tool stack configurations."""

    @staticmethod
    def add(stack_id: str, name: str, tools_enabled: List[str],
            mcp_config: Optional[Dict] = None,
            description: Optional[str] = None) -> int:
        """Add a tool stack."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO tool_stacks
                (stack_id, name, description, tools_enabled, mcp_config)
                VALUES (?, ?, ?, ?, ?)
            """, (stack_id, name, description,
                  json.dumps(tools_enabled),
                  json.dumps(mcp_config) if mcp_config else None))
            return cursor.lastrowid

    @staticmethod
    def get(stack_id: str) -> Optional[Dict]:
        """Get tool stack by ID."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tool_stacks WHERE stack_id = ?", (stack_id,))
            row = cursor.fetchone()
            if row:
                result = dict(row)
                for field in ['tools_enabled', 'mcp_config']:
                    if result.get(field):
                        result[field] = json.loads(result[field])
                return result
            return None

    @staticmethod
    def list_all(active_only: bool = False) -> List[Dict]:
        """List all tool stacks."""
        with get_db() as conn:
            cursor = conn.cursor()
            if active_only:
                cursor.execute("SELECT * FROM tool_stacks WHERE is_active = 1 ORDER BY name")
            else:
                cursor.execute("SELECT * FROM tool_stacks ORDER BY name")
            results = []
            for row in cursor.fetchall():
                result = dict(row)
                for field in ['tools_enabled', 'mcp_config']:
                    if result.get(field):
                        result[field] = json.loads(result[field])
                results.append(result)
            return results

    @staticmethod
    def update(stack_id: str, **kwargs):
        """Update tool stack."""
        valid_fields = {'name', 'description', 'tools_enabled', 'mcp_config', 'is_active'}
        updates = {k: v for k, v in kwargs.items() if k in valid_fields}

        for field in ['tools_enabled', 'mcp_config']:
            if field in updates and isinstance(updates[field], (list, dict)):
                updates[field] = json.dumps(updates[field])

        updates['updated_at'] = datetime.utcnow().isoformat()

        if not updates:
            return

        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [stack_id]

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE tool_stacks SET {set_clause} WHERE stack_id = ?", values)

    @staticmethod
    def deactivate(stack_id: str):
        """Deactivate tool stack."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE tool_stacks SET is_active = 0 WHERE stack_id = ?", (stack_id,))


def seed_default_tool_stacks():
    """Seed default tool stack configurations."""
    stacks = [
        {
            "stack_id": "baseline",
            "name": "Baseline",
            "description": "No MCP tools - pure Claude Code",
            "tools_enabled": ["bash", "read", "edit", "write", "grep", "glob"],
            "mcp_config": None
        },
        {
            "stack_id": "sourcegraph",
            "name": "Sourcegraph MCP",
            "description": "Full Sourcegraph MCP toolkit",
            "tools_enabled": ["bash", "read", "edit", "write", "grep", "glob",
                            "sg_keyword_search", "sg_nls_search", "sg_deepsearch"],
            "mcp_config": {
                "server": "@sourcegraph/mcp-server",
                "endpoints": ["keyword_search", "nls_search", "deep_search"]
            }
        },
        {
            "stack_id": "deepsearch",
            "name": "Deep Search MCP",
            "description": "Deep Search MCP only",
            "tools_enabled": ["bash", "read", "edit", "write", "grep", "glob", "sg_deepsearch"],
            "mcp_config": {
                "server": "@sourcegraph/mcp-server",
                "endpoints": ["deep_search"]
            }
        }
    ]

    for stack in stacks:
        existing = ToolStackRegistry.get(stack["stack_id"])
        if not existing:
            ToolStackRegistry.add(
                stack_id=stack["stack_id"],
                name=stack["name"],
                description=stack["description"],
                tools_enabled=stack["tools_enabled"],
                mcp_config=stack["mcp_config"]
            )


# Initialize database on import
init_database()
# Seed default tool stacks
seed_default_tool_stacks()
