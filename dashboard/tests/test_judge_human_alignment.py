"""
Tests for dashboard.utils.judge_human_alignment.

Covers:
- Database initialization and schema
- Human score CRUD operations
- Score loading and filtering
- Task review counting
- Table data building
- Progress indicator rendering
- Score entry table rendering
- Main tab rendering
"""

import sqlite3
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from dashboard.utils.judge_human_alignment import (
    HUMAN_SCORES_DB,
    HumanScore,
    _build_alignment_table_data,
    _get_db_path,
    _render_progress_indicator,
    _session_key,
    count_reviewed_tasks,
    init_database,
    load_human_scores,
    load_scores_for_tasks,
    save_human_score,
)
from dashboard.utils.judge_test_prompt import (
    DimensionResult,
    TestPromptResult,
)


class TestSessionKey(TestCase):
    """Tests for _session_key."""

    def test_builds_prefixed_key(self):
        result = _session_key("foo")
        self.assertEqual(result, "judge_human_alignment_foo")

    def test_different_suffixes_produce_different_keys(self):
        key1 = _session_key("a")
        key2 = _session_key("b")
        self.assertNotEqual(key1, key2)


class TestGetDbPath(TestCase):
    """Tests for _get_db_path."""

    def test_returns_correct_path(self):
        root = Path("/project")
        result = _get_db_path(root)
        self.assertEqual(result, root / HUMAN_SCORES_DB)


class TestInitDatabase(TestCase):
    """Tests for init_database."""

    def test_creates_table(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            init_database(db_path)

            conn = sqlite3.connect(str(db_path))
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name='human_alignment_scores'"
                )
                result = cursor.fetchone()
                self.assertIsNotNone(result)
            finally:
                conn.close()

    def test_creates_parent_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "subdir" / "test.db"
            init_database(db_path)
            self.assertTrue(db_path.exists())

    def test_idempotent_initialization(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            init_database(db_path)
            init_database(db_path)  # Should not raise

    def test_table_has_correct_columns(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            init_database(db_path)

            conn = sqlite3.connect(str(db_path))
            try:
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(human_alignment_scores)")
                columns = {row[1] for row in cursor.fetchall()}
                expected = {
                    "id", "task_id", "dimension", "human_score",
                    "llm_score", "annotator", "timestamp",
                }
                self.assertEqual(columns, expected)
            finally:
                conn.close()


class TestSaveHumanScore(TestCase):
    """Tests for save_human_score."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = Path(self.tmpdir) / "test.db"
        init_database(self.db_path)

    def test_saves_score(self):
        save_human_score(
            self.db_path, "task_1", "Correctness", 4, "3", "alice"
        )

        scores = load_human_scores(self.db_path)
        self.assertEqual(len(scores), 1)
        self.assertEqual(scores[0].task_id, "task_1")
        self.assertEqual(scores[0].dimension, "Correctness")
        self.assertEqual(scores[0].human_score, 4)
        self.assertEqual(scores[0].llm_score, "3")
        self.assertEqual(scores[0].annotator, "alice")

    def test_upserts_on_duplicate(self):
        save_human_score(
            self.db_path, "task_1", "Correctness", 3, "3", "alice"
        )
        save_human_score(
            self.db_path, "task_1", "Correctness", 5, "3", "alice"
        )

        scores = load_human_scores(self.db_path)
        self.assertEqual(len(scores), 1)
        self.assertEqual(scores[0].human_score, 5)

    def test_different_annotators_are_separate(self):
        save_human_score(
            self.db_path, "task_1", "Correctness", 3, "3", "alice"
        )
        save_human_score(
            self.db_path, "task_1", "Correctness", 4, "3", "bob"
        )

        scores = load_human_scores(self.db_path)
        self.assertEqual(len(scores), 2)

    def test_rejects_score_below_1(self):
        with self.assertRaises(ValueError):
            save_human_score(
                self.db_path, "task_1", "Correctness", 0, "3", "alice"
            )

    def test_rejects_score_above_5(self):
        with self.assertRaises(ValueError):
            save_human_score(
                self.db_path, "task_1", "Correctness", 6, "3", "alice"
            )

    def test_saves_multiple_dimensions(self):
        save_human_score(
            self.db_path, "task_1", "Correctness", 4, "3", "alice"
        )
        save_human_score(
            self.db_path, "task_1", "Quality", 5, "4", "alice"
        )

        scores = load_human_scores(self.db_path)
        self.assertEqual(len(scores), 2)

    def test_stores_timestamp(self):
        save_human_score(
            self.db_path, "task_1", "Correctness", 4, "3", "alice"
        )

        scores = load_human_scores(self.db_path)
        self.assertIsNotNone(scores[0].timestamp)
        self.assertIn("T", scores[0].timestamp)  # ISO format


class TestLoadHumanScores(TestCase):
    """Tests for load_human_scores."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = Path(self.tmpdir) / "test.db"
        init_database(self.db_path)

    def test_returns_empty_for_nonexistent_db(self):
        result = load_human_scores(Path("/nonexistent/db.sqlite"))
        self.assertEqual(result, [])

    def test_returns_all_scores(self):
        save_human_score(self.db_path, "t1", "Dim1", 3, "2", "alice")
        save_human_score(self.db_path, "t2", "Dim1", 4, "3", "alice")

        scores = load_human_scores(self.db_path)
        self.assertEqual(len(scores), 2)

    def test_filters_by_annotator(self):
        save_human_score(self.db_path, "t1", "Dim1", 3, "2", "alice")
        save_human_score(self.db_path, "t1", "Dim1", 4, "2", "bob")

        scores = load_human_scores(self.db_path, annotator="alice")
        self.assertEqual(len(scores), 1)
        self.assertEqual(scores[0].annotator, "alice")

    def test_returns_human_score_dataclass(self):
        save_human_score(self.db_path, "t1", "Dim1", 3, "2", "alice")

        scores = load_human_scores(self.db_path)
        self.assertIsInstance(scores[0], HumanScore)
        self.assertEqual(scores[0].task_id, "t1")
        self.assertEqual(scores[0].dimension, "Dim1")
        self.assertEqual(scores[0].human_score, 3)

    def test_returns_sorted_by_task_and_dimension(self):
        save_human_score(self.db_path, "t2", "Dim2", 3, "2", "alice")
        save_human_score(self.db_path, "t1", "Dim1", 4, "3", "alice")
        save_human_score(self.db_path, "t2", "Dim1", 5, "4", "alice")

        scores = load_human_scores(self.db_path)
        task_dim_pairs = [(s.task_id, s.dimension) for s in scores]
        self.assertEqual(
            task_dim_pairs,
            [("t1", "Dim1"), ("t2", "Dim1"), ("t2", "Dim2")],
        )


class TestLoadScoresForTasks(TestCase):
    """Tests for load_scores_for_tasks."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = Path(self.tmpdir) / "test.db"
        init_database(self.db_path)

    def test_returns_empty_for_nonexistent_db(self):
        result = load_scores_for_tasks(
            Path("/nonexistent/db.sqlite"), ["t1"]
        )
        self.assertEqual(result, {})

    def test_returns_empty_for_empty_task_list(self):
        result = load_scores_for_tasks(self.db_path, [])
        self.assertEqual(result, {})

    def test_returns_scores_for_specified_tasks(self):
        save_human_score(self.db_path, "t1", "Dim1", 3, "2", "alice")
        save_human_score(self.db_path, "t1", "Dim2", 4, "3", "alice")
        save_human_score(self.db_path, "t2", "Dim1", 5, "4", "alice")
        save_human_score(self.db_path, "t3", "Dim1", 2, "1", "alice")

        result = load_scores_for_tasks(self.db_path, ["t1", "t2"])
        self.assertIn("t1", result)
        self.assertIn("t2", result)
        self.assertNotIn("t3", result)
        self.assertEqual(result["t1"]["Dim1"], 3)
        self.assertEqual(result["t1"]["Dim2"], 4)
        self.assertEqual(result["t2"]["Dim1"], 5)

    def test_filters_by_annotator(self):
        save_human_score(self.db_path, "t1", "Dim1", 3, "2", "alice")
        save_human_score(self.db_path, "t1", "Dim1", 5, "2", "bob")

        result = load_scores_for_tasks(
            self.db_path, ["t1"], annotator="bob"
        )
        self.assertEqual(result["t1"]["Dim1"], 5)

    def test_returns_nested_dict_structure(self):
        save_human_score(self.db_path, "t1", "Dim1", 3, "2", "")
        save_human_score(self.db_path, "t1", "Dim2", 4, "3", "")

        result = load_scores_for_tasks(self.db_path, ["t1"])
        self.assertIsInstance(result, dict)
        self.assertIsInstance(result["t1"], dict)
        self.assertEqual(result["t1"]["Dim1"], 3)
        self.assertEqual(result["t1"]["Dim2"], 4)


class TestCountReviewedTasks(TestCase):
    """Tests for count_reviewed_tasks."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = Path(self.tmpdir) / "test.db"
        init_database(self.db_path)

    def test_returns_zero_for_empty(self):
        result = count_reviewed_tasks(
            self.db_path, ["t1"], ["Dim1", "Dim2"]
        )
        self.assertEqual(result, 0)

    def test_returns_zero_for_empty_task_list(self):
        result = count_reviewed_tasks(self.db_path, [], ["Dim1"])
        self.assertEqual(result, 0)

    def test_returns_zero_for_empty_dimensions(self):
        result = count_reviewed_tasks(self.db_path, ["t1"], [])
        self.assertEqual(result, 0)

    def test_counts_fully_reviewed_tasks(self):
        # t1 fully reviewed (both dimensions)
        save_human_score(self.db_path, "t1", "Dim1", 3, "2", "")
        save_human_score(self.db_path, "t1", "Dim2", 4, "3", "")
        # t2 partially reviewed (only one dimension)
        save_human_score(self.db_path, "t2", "Dim1", 5, "4", "")

        result = count_reviewed_tasks(
            self.db_path, ["t1", "t2"], ["Dim1", "Dim2"]
        )
        self.assertEqual(result, 1)

    def test_counts_all_reviewed(self):
        save_human_score(self.db_path, "t1", "Dim1", 3, "2", "")
        save_human_score(self.db_path, "t2", "Dim1", 4, "3", "")

        result = count_reviewed_tasks(
            self.db_path, ["t1", "t2"], ["Dim1"]
        )
        self.assertEqual(result, 2)

    def test_filters_by_annotator(self):
        save_human_score(self.db_path, "t1", "Dim1", 3, "2", "alice")
        save_human_score(self.db_path, "t1", "Dim1", 4, "2", "bob")

        result = count_reviewed_tasks(
            self.db_path, ["t1"], ["Dim1"], annotator="alice"
        )
        self.assertEqual(result, 1)


class TestBuildAlignmentTableData(TestCase):
    """Tests for _build_alignment_table_data."""

    def _make_result(self, task_id, dim_scores):
        """Helper to create a TestPromptResult."""
        dim_results = tuple(
            DimensionResult(name=name, score=score, reasoning="")
            for name, score in dim_scores
        )
        return TestPromptResult(
            task_id=task_id,
            dimension_results=dim_results,
            overall_score="3",
            overall_reasoning="",
        )

    def test_builds_rows_with_llm_and_human_scores(self):
        tasks = [("t1", Path("/t1")), ("t2", Path("/t2"))]
        llm_results = {
            "t1": self._make_result("t1", [("Dim1", "4"), ("Dim2", "3")]),
            "t2": self._make_result("t2", [("Dim1", "2"), ("Dim2", "5")]),
        }
        human_scores = {
            "t1": {"Dim1": 3, "Dim2": 4},
        }
        dimensions = ["Dim1", "Dim2"]

        rows = _build_alignment_table_data(
            tasks, llm_results, human_scores, dimensions
        )

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["Task ID"], "t1")
        self.assertEqual(rows[0]["LLM: Dim1"], "4")
        self.assertEqual(rows[0]["Human: Dim1"], 3)
        self.assertEqual(rows[0]["LLM: Dim2"], "3")
        self.assertEqual(rows[0]["Human: Dim2"], 4)

    def test_shows_dash_for_missing_human_scores(self):
        tasks = [("t1", Path("/t1"))]
        llm_results = {
            "t1": self._make_result("t1", [("Dim1", "4")]),
        }
        human_scores = {}
        dimensions = ["Dim1"]

        rows = _build_alignment_table_data(
            tasks, llm_results, human_scores, dimensions
        )

        self.assertEqual(rows[0]["Human: Dim1"], "-")

    def test_shows_na_for_missing_llm_results(self):
        tasks = [("t1", Path("/t1"))]
        llm_results = {}
        human_scores = {}
        dimensions = ["Dim1"]

        rows = _build_alignment_table_data(
            tasks, llm_results, human_scores, dimensions
        )

        self.assertEqual(rows[0]["LLM: Dim1"], "N/A")

    def test_empty_tasks_returns_empty(self):
        rows = _build_alignment_table_data([], {}, {}, ["Dim1"])
        self.assertEqual(rows, [])


class TestRenderProgressIndicator(TestCase):
    """Tests for _render_progress_indicator."""

    @patch("dashboard.utils.judge_human_alignment.st")
    def test_renders_progress_bar(self, mock_st):
        _render_progress_indicator(3, 10)

        mock_st.progress.assert_called_once_with(0.3)
        mock_st.caption.assert_called_once_with("3 of 10 tasks reviewed")

    @patch("dashboard.utils.judge_human_alignment.st")
    def test_renders_full_progress(self, mock_st):
        _render_progress_indicator(5, 5)

        mock_st.progress.assert_called_once_with(1.0)
        mock_st.caption.assert_called_once_with("5 of 5 tasks reviewed")

    @patch("dashboard.utils.judge_human_alignment.st")
    def test_handles_zero_total(self, mock_st):
        _render_progress_indicator(0, 0)

        mock_st.info.assert_called_once_with("No tasks to review.")


class TestRenderScoreEntryTable(TestCase):
    """Tests for _render_score_entry_table via integration."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = Path(self.tmpdir) / "test.db"
        init_database(self.db_path)

    def test_save_and_reload_workflow(self):
        """Test the full save-then-load workflow."""
        # Save scores
        save_human_score(self.db_path, "t1", "Correctness", 4, "3", "tester")
        save_human_score(self.db_path, "t1", "Quality", 5, "4", "tester")
        save_human_score(self.db_path, "t2", "Correctness", 3, "2", "tester")

        # Reload
        scores = load_scores_for_tasks(
            self.db_path, ["t1", "t2"], annotator="tester"
        )

        self.assertEqual(scores["t1"]["Correctness"], 4)
        self.assertEqual(scores["t1"]["Quality"], 5)
        self.assertEqual(scores["t2"]["Correctness"], 3)

    def test_count_reviewed_full_workflow(self):
        """Test review counting with multi-dimension requirements."""
        dims = ["Correctness", "Quality", "Completeness"]

        # t1: all 3 dimensions scored -> reviewed
        save_human_score(self.db_path, "t1", "Correctness", 4, "3", "")
        save_human_score(self.db_path, "t1", "Quality", 5, "4", "")
        save_human_score(self.db_path, "t1", "Completeness", 3, "3", "")

        # t2: only 2 of 3 dimensions -> not reviewed
        save_human_score(self.db_path, "t2", "Correctness", 3, "2", "")
        save_human_score(self.db_path, "t2", "Quality", 4, "3", "")

        # t3: no scores -> not reviewed

        reviewed = count_reviewed_tasks(
            self.db_path, ["t1", "t2", "t3"], dims
        )
        self.assertEqual(reviewed, 1)


class TestHumanScoreDataclass(TestCase):
    """Tests for the HumanScore frozen dataclass."""

    def test_is_frozen(self):
        score = HumanScore(
            task_id="t1",
            dimension="Dim1",
            human_score=4,
            llm_score="3",
            annotator="alice",
            timestamp="2026-01-27T12:00:00Z",
        )
        with self.assertRaises(AttributeError):
            score.human_score = 5  # type: ignore

    def test_equality(self):
        score1 = HumanScore("t1", "Dim1", 4, "3", "alice", "2026-01-27T12:00:00Z")
        score2 = HumanScore("t1", "Dim1", 4, "3", "alice", "2026-01-27T12:00:00Z")
        self.assertEqual(score1, score2)


class TestDatabaseConstraints(TestCase):
    """Tests for database constraints."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = Path(self.tmpdir) / "test.db"
        init_database(self.db_path)

    def test_unique_constraint_on_task_dimension_annotator(self):
        """Verify UNIQUE(task_id, dimension, annotator) is enforced."""
        save_human_score(self.db_path, "t1", "Dim1", 3, "2", "alice")
        save_human_score(self.db_path, "t1", "Dim1", 5, "2", "alice")

        # Should have only 1 row (upserted)
        scores = load_human_scores(self.db_path, annotator="alice")
        self.assertEqual(len(scores), 1)
        self.assertEqual(scores[0].human_score, 5)

    def test_check_constraint_on_score_range(self):
        """Verify CHECK(human_score BETWEEN 1 AND 5) is enforced at DB level."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.cursor()
            with self.assertRaises(sqlite3.IntegrityError):
                cursor.execute(
                    """
                    INSERT INTO human_alignment_scores
                        (task_id, dimension, human_score, llm_score, annotator, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    ("t1", "Dim1", 0, "3", "alice", "2026-01-27"),
                )
        finally:
            conn.close()

    def test_check_constraint_high_score(self):
        """Verify CHECK constraint blocks scores > 5."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.cursor()
            with self.assertRaises(sqlite3.IntegrityError):
                cursor.execute(
                    """
                    INSERT INTO human_alignment_scores
                        (task_id, dimension, human_score, llm_score, annotator, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    ("t1", "Dim1", 6, "3", "alice", "2026-01-27"),
                )
        finally:
            conn.close()


class TestRenderHumanAlignmentTab(TestCase):
    """Tests for render_human_alignment_tab."""

    @patch("dashboard.utils.judge_human_alignment.st")
    @patch("dashboard.utils.judge_human_alignment.list_template_infos")
    @patch("dashboard.utils.judge_human_alignment.init_database")
    def test_shows_info_when_no_templates(
        self, mock_init_db, mock_list_infos, mock_st
    ):
        mock_list_infos.return_value = []
        mock_st.session_state = {}
        mock_st.text_input.return_value = "tester"

        from dashboard.utils.judge_human_alignment import (
            render_human_alignment_tab,
        )

        render_human_alignment_tab(Path("/project"))

        mock_st.info.assert_called()
        # Should show message about needing templates
        info_calls = [
            str(call) for call in mock_st.info.call_args_list
        ]
        self.assertTrue(
            any("template" in str(c).lower() for c in info_calls)
        )


class TestTabIntegration(TestCase):
    """Tests for integration with analysis_llm_judge.py."""

    def test_import_render_function(self):
        """Verify the render function can be imported."""
        from dashboard.utils.judge_human_alignment import (
            render_human_alignment_tab,
        )

        self.assertTrue(callable(render_human_alignment_tab))

    def test_import_in_analysis_view(self):
        """Verify the analysis view imports the alignment tab."""
        # This checks the import statement works
        import importlib

        mod = importlib.import_module("dashboard.views.analysis_llm_judge")
        self.assertTrue(hasattr(mod, "render_human_alignment_tab"))
