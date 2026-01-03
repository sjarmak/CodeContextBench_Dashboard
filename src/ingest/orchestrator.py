"""
Orchestrate the ingestion pipeline for Harbor results and transcripts.

Discovers Harbor result files and transcripts, parses them, and stores
metrics in the database.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime

from .harbor_parser import HarborResultParser
from .transcript_parser import TranscriptParser
from .database import MetricsDatabase


logger = logging.getLogger(__name__)


class IngestionOrchestrator:
    """Orchestrate ingestion of Harbor results and transcripts."""
    
    def __init__(
        self,
        db_path: Path,
        results_dir: Optional[Path] = None,
        transcripts_dir: Optional[Path] = None,
    ):
        """
        Initialize the orchestrator.
        
        Args:
            db_path: Path to SQLite database
            results_dir: Path to Harbor results directory
            transcripts_dir: Path to transcripts directory
        """
        self.db = MetricsDatabase(db_path)
        self.results_dir = results_dir
        self.transcripts_dir = transcripts_dir
        self.parser = HarborResultParser()
        self.transcript_parser = TranscriptParser()
    
    def ingest_experiment(
        self,
        experiment_id: str,
        results_dir: Optional[Path] = None,
    ) -> dict:
        """
        Ingest all results for an experiment.
        
        Args:
            experiment_id: Experiment identifier
            results_dir: Optional override for results directory
            
        Returns:
            Statistics about the ingestion
        """
        if results_dir is None:
            results_dir = self.results_dir
        
        if results_dir is None:
            raise ValueError("results_dir must be provided")
        
        logger.info(f"Starting ingestion for experiment: {experiment_id}")
        
        stats = {
            "experiment_id": experiment_id,
            "results_processed": 0,
            "results_skipped": 0,
            "transcripts_processed": 0,
            "transcripts_skipped": 0,
            "errors": [],
            "started_at": datetime.utcnow().isoformat(),
        }
        
        # Find and process harbor result files
        for result_file in results_dir.glob("**/result.json"):
            try:
                job_id = self._extract_job_id(result_file)
                if not job_id:
                    logger.warning(f"Skipping {result_file}: could not extract job_id")
                    stats["results_skipped"] += 1
                    continue
                
                # Parse the result
                result = self.parser.parse_file(result_file)
                
                # Store in database
                self.db.store_harbor_result(
                    result,
                    experiment_id=experiment_id,
                    job_id=job_id,
                )
                
                # Look for corresponding transcript
                transcript_file = result_file.parent / "claude-code.txt"
                if transcript_file.exists():
                    try:
                        metrics = self.transcript_parser.parse_file(transcript_file)
                        self.db.store_tool_usage(
                            task_id=result.task_id,
                            metrics=metrics,
                            experiment_id=experiment_id,
                            job_id=job_id,
                        )
                        stats["transcripts_processed"] += 1
                    except Exception as e:
                        logger.error(f"Error processing transcript {transcript_file}: {e}")
                        stats["transcripts_skipped"] += 1
                        stats["errors"].append(f"Transcript error: {str(e)}")
                else:
                    stats["transcripts_skipped"] += 1
                
                stats["results_processed"] += 1
                logger.debug(f"Ingested {result.task_id} (job={job_id})")
                
            except Exception as e:
                logger.error(f"Error processing {result_file}: {e}")
                stats["results_skipped"] += 1
                stats["errors"].append(f"Result error: {str(e)}")
        
        # Update experiment summary
        try:
            self.db.update_experiment_summary(experiment_id)
            logger.info(f"Updated experiment summary for {experiment_id}")
        except Exception as e:
            logger.error(f"Error updating experiment summary: {e}")
            stats["errors"].append(f"Summary error: {str(e)}")
        
        stats["ended_at"] = datetime.utcnow().isoformat()
        
        logger.info(
            f"Ingestion complete. Results: {stats['results_processed']}, "
            f"Transcripts: {stats['transcripts_processed']}, "
            f"Errors: {len(stats['errors'])}"
        )
        
        return stats
    
    def ingest_directory(
        self,
        results_dir: Path,
        experiment_pattern: Optional[str] = None,
    ) -> dict:
        """
        Ingest all experiments from a directory structure.
        
        Args:
            results_dir: Base results directory
            experiment_pattern: Optional pattern to match experiment directories
            
        Returns:
            Statistics for all experiments
        """
        logger.info(f"Discovering experiments in {results_dir}")
        
        all_stats = {
            "experiments": [],
            "total_results": 0,
            "total_transcripts": 0,
            "total_errors": 0,
        }
        
        # Look for experiment directories
        for exp_dir in results_dir.iterdir():
            if not exp_dir.is_dir():
                continue
            
            if experiment_pattern and not exp_dir.name.startswith(experiment_pattern):
                continue
            
            try:
                stats = self.ingest_experiment(
                    experiment_id=exp_dir.name,
                    results_dir=exp_dir,
                )
                all_stats["experiments"].append(stats)
                all_stats["total_results"] += stats["results_processed"]
                all_stats["total_transcripts"] += stats["transcripts_processed"]
                all_stats["total_errors"] += len(stats["errors"])
            except Exception as e:
                logger.error(f"Error processing experiment {exp_dir.name}: {e}")
                all_stats["total_errors"] += 1
        
        return all_stats
    
    def _extract_job_id(self, result_file: Path) -> Optional[str]:
        """Extract job ID from result file path."""
        # Try various path patterns
        # Pattern: jobs/{job_id}/result.json
        if result_file.parent.parent.name == "jobs":
            return result_file.parent.name
        
        # Pattern: {experiment}/{job_id}/result.json
        return result_file.parent.name
    
    def get_experiment_stats(self, experiment_id: str) -> dict:
        """Get statistics for an experiment."""
        return self.db.get_stats(experiment_id)
    
    def get_experiment_results(self, experiment_id: str) -> list[dict]:
        """Get all results for an experiment."""
        return self.db.get_experiment_results(experiment_id)
