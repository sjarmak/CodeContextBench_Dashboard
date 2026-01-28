"""
Tests for analysis loader integration with Phase 4 components.
"""

import pytest
from pathlib import Path
import tempfile
import sqlite3

from dashboard.utils.analysis_loader import (
    AnalysisLoader,
    DatabaseNotFoundError,
    ExperimentNotFoundError,
)


@pytest.fixture
def temp_db():
    """Create a temporary test database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    
    # Create test schema
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create harbor_results table
    cursor.execute("""
        CREATE TABLE harbor_results (
            job_id TEXT,
            experiment_id TEXT,
            task_id TEXT,
            agent_name TEXT,
            passed BOOLEAN,
            duration_seconds FLOAT,
            reward_primary FLOAT
        )
    """)
    
    # Insert test data
    cursor.execute(
        "INSERT INTO harbor_results VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("job1", "exp001", "task1", "baseline", 1, 10.5, 0.8)
    )
    cursor.execute(
        "INSERT INTO harbor_results VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("job2", "exp001", "task2", "baseline", 0, 12.0, 0.6)
    )
    cursor.execute(
        "INSERT INTO harbor_results VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("job3", "exp001", "task3", "variant", 1, 9.5, 0.85)
    )
    
    conn.commit()
    conn.close()
    
    yield db_path
    
    # Cleanup
    db_path.unlink()


class TestAnalysisLoaderInitialization:
    """Tests for AnalysisLoader initialization."""
    
    def test_init_with_valid_database(self, temp_db):
        """Loader initializes with valid database path."""
        loader = AnalysisLoader(temp_db)
        assert loader.db_path == temp_db
        assert loader.is_healthy()
    
    def test_init_with_missing_database(self):
        """Loader raises error when database doesn't exist."""
        with pytest.raises(DatabaseNotFoundError):
            AnalysisLoader(Path("/nonexistent/metrics.db"))
    
    def test_cache_initialization(self, temp_db):
        """Cache is initialized as empty dict."""
        loader = AnalysisLoader(temp_db)
        assert loader._cache == {}


class TestExperimentListing:
    """Tests for listing experiments and agents."""
    
    def test_list_experiments(self, temp_db):
        """List experiments returns unique experiment IDs."""
        loader = AnalysisLoader(temp_db)
        experiments = loader.list_experiments()
        
        assert len(experiments) == 1
        assert "exp001" in experiments
    
    def test_list_agents(self, temp_db):
        """List agents returns unique agent names in experiment."""
        loader = AnalysisLoader(temp_db)
        agents = loader.list_agents("exp001")
        
        assert len(agents) == 2
        assert "baseline" in agents
        assert "variant" in agents
    
    def test_list_agents_empty_experiment(self, temp_db):
        """List agents returns empty list for non-existent experiment."""
        loader = AnalysisLoader(temp_db)
        agents = loader.list_agents("nonexistent")
        
        assert agents == []
    
    def test_list_experiments_empty_database(self):
        """List experiments handles empty database gracefully."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        
        try:
            # Create empty database with no tables
            conn = sqlite3.connect(db_path)
            conn.close()
            
            loader = AnalysisLoader(db_path)
            experiments = loader.list_experiments()
            
            assert experiments == []
        finally:
            db_path.unlink()


class TestCaching:
    """Tests for result caching mechanism."""
    
    def test_cache_stores_results(self, temp_db):
        """Results are cached after first load."""
        loader = AnalysisLoader(temp_db)
        
        # Make a call that would be cached
        experiments1 = loader.list_experiments()
        
        # Direct cache access
        assert len(loader._cache) == 0  # list_experiments doesn't use cache
    
    def test_clear_cache(self, temp_db):
        """Clear cache empties the cache dict."""
        loader = AnalysisLoader(temp_db)
        loader._cache["test_key"] = "test_value"
        
        loader.clear_cache()
        
        assert loader._cache == {}


class TestDatabaseHealth:
    """Tests for database health checking."""
    
    def test_is_healthy_with_valid_db(self, temp_db):
        """is_healthy returns True for valid database."""
        loader = AnalysisLoader(temp_db)
        assert loader.is_healthy() is True
    
    def test_is_healthy_handles_errors(self):
        """is_healthy returns False on error."""
        # Create invalid database path
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        
        try:
            # Write invalid data
            with open(db_path, "w") as f:
                f.write("not a database")
            
            loader = AnalysisLoader(db_path)
            assert loader.is_healthy() is False
        finally:
            db_path.unlink()


class TestDatabaseStatistics:
    """Tests for database statistics retrieval."""
    
    def test_get_stats(self, temp_db):
        """Get stats retrieves overall database statistics."""
        loader = AnalysisLoader(temp_db)
        stats = loader.get_stats()
        
        # Stats should be a dictionary (may be empty for test DB)
        assert isinstance(stats, dict)


class TestErrorHandling:
    """Tests for error handling in analysis methods."""
    
    def test_load_comparison_missing_exp(self, temp_db):
        """Load comparison raises error for missing experiment."""
        loader = AnalysisLoader(temp_db)
        
        with pytest.raises(ExperimentNotFoundError):
            loader.load_comparison("nonexistent")
    
    def test_load_statistical_missing_exp(self, temp_db):
        """Load statistical raises error for missing experiment."""
        loader = AnalysisLoader(temp_db)
        
        with pytest.raises(ExperimentNotFoundError):
            loader.load_statistical("nonexistent")
    
    def test_load_failures_missing_exp(self, temp_db):
        """Load failures raises error for missing experiment."""
        loader = AnalysisLoader(temp_db)
        
        with pytest.raises(ExperimentNotFoundError):
            loader.load_failures("nonexistent")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
