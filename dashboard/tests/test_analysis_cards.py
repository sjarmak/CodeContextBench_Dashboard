"""
Tests for dashboard/utils/analysis_cards.py

Tests:
- AnalysisCard dataclass immutability and field access
- ANALYSIS_CARDS constant: 6 cards, correct page_name values
- check_results_available: session state checks, filesystem fallback
- _check_db_has_experiments: loader presence and experiment count
- _check_judge_results_exist: judge results directory check
- _render_status_badge: HTML output for available/unavailable
- render_analysis_card: card HTML and button rendering
- render_analysis_card_grid: 2x3 grid layout
- Integration with analysis_hub.py
"""

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from dashboard.utils.analysis_cards import (
    ANALYSIS_CARDS,
    AnalysisCard,
    _check_db_has_experiments,
    _check_judge_results_exist,
    _render_status_badge,
    check_results_available,
    render_analysis_card,
    render_analysis_card_grid,
)


class TestAnalysisCard(unittest.TestCase):
    """Test AnalysisCard frozen dataclass."""

    def test_field_access(self):
        card = AnalysisCard(
            card_id="test",
            title="Test Card",
            icon="T",
            description="A test card",
            page_name="Test Page",
            status_key="test_results",
        )
        self.assertEqual(card.card_id, "test")
        self.assertEqual(card.title, "Test Card")
        self.assertEqual(card.icon, "T")
        self.assertEqual(card.description, "A test card")
        self.assertEqual(card.page_name, "Test Page")
        self.assertEqual(card.status_key, "test_results")

    def test_immutability(self):
        card = AnalysisCard(
            card_id="test",
            title="Test",
            icon="T",
            description="desc",
            page_name="Page",
            status_key="key",
        )
        with self.assertRaises(AttributeError):
            card.title = "Modified"

    def test_equality(self):
        card1 = AnalysisCard("a", "A", "i", "d", "p", "k")
        card2 = AnalysisCard("a", "A", "i", "d", "p", "k")
        self.assertEqual(card1, card2)


class TestAnalysisCardsConstant(unittest.TestCase):
    """Test ANALYSIS_CARDS tuple."""

    def test_has_six_cards(self):
        self.assertEqual(len(ANALYSIS_CARDS), 6)

    def test_card_ids_unique(self):
        ids = [c.card_id for c in ANALYSIS_CARDS]
        self.assertEqual(len(ids), len(set(ids)))

    def test_page_names_match_app_navigation(self):
        """Page names must match the nav_items_analysis in app.py."""
        expected_pages = {
            "Statistical Analysis",
            "Comparison Analysis",
            "Time-Series Analysis",
            "Cost Analysis",
            "Failure Analysis",
            "LLM Judge",
        }
        actual_pages = {c.page_name for c in ANALYSIS_CARDS}
        self.assertEqual(actual_pages, expected_pages)

    def test_all_cards_have_icons(self):
        for card in ANALYSIS_CARDS:
            self.assertTrue(len(card.icon) > 0, f"{card.card_id} missing icon")

    def test_all_cards_have_descriptions(self):
        for card in ANALYSIS_CARDS:
            self.assertTrue(
                len(card.description) > 0, f"{card.card_id} missing description"
            )

    def test_status_keys_unique(self):
        keys = [c.status_key for c in ANALYSIS_CARDS]
        self.assertEqual(len(keys), len(set(keys)))


class TestCheckResultsAvailable(unittest.TestCase):
    """Test check_results_available function."""

    @patch("dashboard.utils.analysis_cards.st")
    def test_returns_true_when_session_state_has_results(self, mock_st):
        mock_st.session_state = {"test_results": {"some": "data"}}
        self.assertTrue(check_results_available("test_results"))

    @patch("dashboard.utils.analysis_cards.st")
    def test_returns_false_when_session_state_empty(self, mock_st):
        mock_st.session_state = {}
        self.assertFalse(check_results_available("test_results"))

    @patch("dashboard.utils.analysis_cards.st")
    def test_returns_false_when_session_state_value_falsy(self, mock_st):
        mock_st.session_state = {"test_results": None}
        self.assertFalse(check_results_available("test_results"))

    @patch("dashboard.utils.analysis_cards.st")
    def test_returns_false_without_project_root(self, mock_st):
        mock_st.session_state = {}
        self.assertFalse(check_results_available("statistical_results"))

    @patch("dashboard.utils.analysis_cards._check_db_has_experiments")
    @patch("dashboard.utils.analysis_cards.st")
    def test_falls_back_to_filesystem_check(self, mock_st, mock_check):
        mock_st.session_state = {}
        mock_check.return_value = True
        root = Path("/tmp/test")
        self.assertTrue(check_results_available("statistical_results", root))
        mock_check.assert_called_once_with(root)

    @patch("dashboard.utils.analysis_cards._check_judge_results_exist")
    @patch("dashboard.utils.analysis_cards.st")
    def test_judge_results_use_judge_checker(self, mock_st, mock_check):
        mock_st.session_state = {}
        mock_check.return_value = True
        root = Path("/tmp/test")
        self.assertTrue(check_results_available("llm_judge_results", root))
        mock_check.assert_called_once_with(root)

    @patch("dashboard.utils.analysis_cards.st")
    def test_unknown_status_key_returns_false(self, mock_st):
        mock_st.session_state = {}
        self.assertFalse(check_results_available("unknown_key", Path("/tmp")))


class TestCheckDbHasExperiments(unittest.TestCase):
    """Test _check_db_has_experiments function."""

    @patch("dashboard.utils.analysis_cards.st")
    def test_returns_false_when_no_loader(self, mock_st):
        mock_st.session_state = {}
        self.assertFalse(_check_db_has_experiments(Path("/tmp")))

    @patch("dashboard.utils.analysis_cards.st")
    def test_returns_true_when_experiments_exist(self, mock_st):
        mock_loader = MagicMock()
        mock_loader.list_experiments.return_value = ["exp1", "exp2"]
        mock_st.session_state = {"analysis_loader": mock_loader}
        self.assertTrue(_check_db_has_experiments(Path("/tmp")))

    @patch("dashboard.utils.analysis_cards.st")
    def test_returns_false_when_no_experiments(self, mock_st):
        mock_loader = MagicMock()
        mock_loader.list_experiments.return_value = []
        mock_st.session_state = {"analysis_loader": mock_loader}
        self.assertFalse(_check_db_has_experiments(Path("/tmp")))

    @patch("dashboard.utils.analysis_cards.st")
    def test_returns_false_on_exception(self, mock_st):
        mock_loader = MagicMock()
        mock_loader.list_experiments.side_effect = Exception("db error")
        mock_st.session_state = {"analysis_loader": mock_loader}
        self.assertFalse(_check_db_has_experiments(Path("/tmp")))


class TestCheckJudgeResultsExist(unittest.TestCase):
    """Test _check_judge_results_exist function."""

    def test_returns_false_when_dir_missing(self):
        self.assertFalse(_check_judge_results_exist(Path("/nonexistent/path")))

    @patch("pathlib.Path.glob")
    @patch("pathlib.Path.exists")
    def test_returns_true_when_json_files_exist(self, mock_exists, mock_glob):
        mock_exists.return_value = True
        mock_glob.return_value = [Path("result1.json"), Path("result2.json")]
        self.assertTrue(_check_judge_results_exist(Path("/tmp/project")))

    @patch("pathlib.Path.glob")
    @patch("pathlib.Path.exists")
    def test_returns_false_when_no_json_files(self, mock_exists, mock_glob):
        mock_exists.return_value = True
        mock_glob.return_value = []
        self.assertFalse(_check_judge_results_exist(Path("/tmp/project")))


class TestRenderStatusBadge(unittest.TestCase):
    """Test _render_status_badge function."""

    def test_available_badge_is_green(self):
        html = _render_status_badge(True)
        self.assertIn("#2ca02c", html)
        self.assertIn("Results Available", html)

    def test_unavailable_badge_is_gray(self):
        html = _render_status_badge(False)
        self.assertIn("#888", html)
        self.assertIn("No Results", html)

    def test_badges_are_html_spans(self):
        for val in (True, False):
            html = _render_status_badge(val)
            self.assertTrue(html.startswith("<span"))
            self.assertTrue(html.endswith("</span>"))


class TestRenderAnalysisCard(unittest.TestCase):
    """Test render_analysis_card function."""

    @patch("dashboard.utils.analysis_cards.st")
    def test_renders_card_html(self, mock_st):
        card = AnalysisCard("test", "Test", "T", "desc", "Page", "key")
        mock_st.button.return_value = False
        render_analysis_card(card, has_results=True)
        mock_st.markdown.assert_called_once()
        html_arg = mock_st.markdown.call_args[0][0]
        self.assertIn("Test", html_arg)
        self.assertIn("desc", html_arg)
        self.assertIn("T", html_arg)

    @patch("dashboard.utils.analysis_cards.st")
    def test_renders_configure_button(self, mock_st):
        card = AnalysisCard("test", "Test", "T", "desc", "Page", "key")
        mock_st.button.return_value = False
        render_analysis_card(card, has_results=False)
        mock_st.button.assert_called_once_with(
            "Configure & Run",
            key="analysis_card_test",
            use_container_width=True,
        )

    @patch("dashboard.utils.analysis_cards.st")
    def test_button_click_navigates(self, mock_st):
        card = AnalysisCard("test", "Test", "T", "desc", "Test Page", "key")
        mock_st.button.return_value = True
        mock_st.session_state = {}
        render_analysis_card(card, has_results=False)
        self.assertEqual(mock_st.session_state["current_page"], "Test Page")
        mock_st.rerun.assert_called_once()

    @patch("dashboard.utils.analysis_cards.st")
    def test_custom_session_key(self, mock_st):
        card = AnalysisCard("test", "Test", "T", "desc", "Page", "key")
        mock_st.button.return_value = True
        mock_st.session_state = {}
        render_analysis_card(card, has_results=False, session_key="custom_key")
        self.assertEqual(mock_st.session_state["custom_key"], "Page")

    @patch("dashboard.utils.analysis_cards.st")
    def test_green_border_when_results_available(self, mock_st):
        card = AnalysisCard("test", "Test", "T", "desc", "Page", "key")
        mock_st.button.return_value = False
        render_analysis_card(card, has_results=True)
        html_arg = mock_st.markdown.call_args[0][0]
        self.assertIn("#2ca02c", html_arg)

    @patch("dashboard.utils.analysis_cards.st")
    def test_gray_border_when_no_results(self, mock_st):
        card = AnalysisCard("test", "Test", "T", "desc", "Page", "key")
        mock_st.button.return_value = False
        render_analysis_card(card, has_results=False)
        html_arg = mock_st.markdown.call_args[0][0]
        self.assertIn("#ddd", html_arg)


class TestRenderAnalysisCardGrid(unittest.TestCase):
    """Test render_analysis_card_grid function."""

    @patch("dashboard.utils.analysis_cards.render_analysis_card")
    @patch("dashboard.utils.analysis_cards.check_results_available")
    @patch("dashboard.utils.analysis_cards.st")
    def test_renders_two_rows(self, mock_st, mock_check, mock_render):
        mock_check.return_value = False
        mock_col = MagicMock()
        mock_st.columns.return_value = [mock_col, mock_col, mock_col]
        render_analysis_card_grid()
        # 2 rows of 3 columns each
        self.assertEqual(mock_st.columns.call_count, 2)

    @patch("dashboard.utils.analysis_cards.render_analysis_card")
    @patch("dashboard.utils.analysis_cards.check_results_available")
    @patch("dashboard.utils.analysis_cards.st")
    def test_renders_all_six_cards(self, mock_st, mock_check, mock_render):
        mock_check.return_value = False
        mock_col = MagicMock()
        mock_st.columns.return_value = [mock_col, mock_col, mock_col]
        render_analysis_card_grid()
        self.assertEqual(mock_render.call_count, 6)

    @patch("dashboard.utils.analysis_cards.render_analysis_card")
    @patch("dashboard.utils.analysis_cards.check_results_available")
    @patch("dashboard.utils.analysis_cards.st")
    def test_passes_project_root_to_check(self, mock_st, mock_check, mock_render):
        mock_check.return_value = False
        mock_col = MagicMock()
        mock_st.columns.return_value = [mock_col, mock_col, mock_col]
        root = Path("/test/root")
        render_analysis_card_grid(project_root=root)
        for call in mock_check.call_args_list:
            self.assertEqual(call[0][1], root)

    @patch("dashboard.utils.analysis_cards.render_analysis_card")
    @patch("dashboard.utils.analysis_cards.check_results_available")
    @patch("dashboard.utils.analysis_cards.st")
    def test_passes_session_key_to_cards(self, mock_st, mock_check, mock_render):
        mock_check.return_value = False
        mock_col = MagicMock()
        mock_st.columns.return_value = [mock_col, mock_col, mock_col]
        render_analysis_card_grid(session_key="my_key")
        for call in mock_render.call_args_list:
            self.assertEqual(call[0][2], "my_key")


class TestAnalysisHubIntegration(unittest.TestCase):
    """Test integration with analysis_hub.py."""

    def test_analysis_hub_imports_card_grid(self):
        """Verify analysis_hub.py imports the card grid function."""
        from dashboard.views.analysis_hub import render_analysis_card_grid as imported
        self.assertIs(imported, render_analysis_card_grid)

    def test_card_page_names_in_app_routes(self):
        """Verify all card page names are routable in app.py."""
        # These are the page names from app.py nav_items_analysis
        routable_pages = {
            "Analysis Hub",
            "LLM Judge",
            "Comparison Analysis",
            "Statistical Analysis",
            "Time-Series Analysis",
            "Cost Analysis",
            "Failure Analysis",
        }
        for card in ANALYSIS_CARDS:
            self.assertIn(
                card.page_name,
                routable_pages,
                f"Card '{card.card_id}' page_name '{card.page_name}' not in app routes",
            )


if __name__ == "__main__":
    unittest.main()
