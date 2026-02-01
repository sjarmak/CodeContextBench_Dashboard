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
from .trajectory_parser import TrajectoryParser
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
        self.trajectory_parser = TrajectoryParser()
    
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

                # Extract agent variant name from path (e.g., "baseline", "deepsearch")
                # This overrides the generic "claude-code" from result.json
                agent_variant = self._extract_agent_name_from_path(result_file, results_dir)
                if agent_variant:
                    result.agent_name = agent_variant

                # Store in database
                self.db.store_harbor_result(
                    result,
                    experiment_id=experiment_id,
                    job_id=job_id,
                )
                
                # Look for corresponding transcript
                # Try multiple locations: agent/claude-code.txt (Harbor format) or claude-code.txt (legacy)
                transcript_file = result_file.parent / "agent" / "claude-code.txt"
                if not transcript_file.exists():
                    transcript_file = result_file.parent / "claude-code.txt"

                if transcript_file.exists():
                    try:
                        metrics = self.transcript_parser.parse_file(transcript_file)

                        # Look for trajectory.json for detailed token metrics
                        # trajectory.json is in same directory as claude-code.txt
                        trajectory_file = transcript_file.parent / "trajectory.json"
                        if trajectory_file.exists():
                            try:
                                trajectory_metrics = self.trajectory_parser.parse_file(trajectory_file)
                                if trajectory_metrics:
                                    metrics.merge_trajectory_metrics(trajectory_metrics)
                                    logger.debug(f"Merged trajectory metrics for {result.task_id}")
                            except Exception as e:
                                logger.warning(f"Error parsing trajectory {trajectory_file}: {e}")

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
        # Pattern: runs/{job_id}/result.json
        if result_file.parent.parent.name == "runs":
            return result_file.parent.name

        # Pattern: {experiment}/{job_id}/result.json
        return result_file.parent.name

    def _extract_agent_name_from_path(self, result_file: Path, results_dir: Path) -> Optional[str]:
        """
        Extract agent variant name from directory structure.

        Supports patterns like:
        - {experiment}/baseline/{timestamp}/{task_id}/result.json -> "baseline"
        - {experiment}/deepsearch/{timestamp}/{task_id}/result.json -> "deepsearch"
        - {experiment}/{task_id}/result.json -> None (use result.json agent_info)

        Args:
            result_file: Path to result.json
            results_dir: Base experiment directory

        Returns:
            Agent variant name or None if not found in path
        """
        try:
            # Get the relative path from results_dir to result_file
            rel_path = result_file.relative_to(results_dir)
            parts = rel_path.parts

            # Check for agent variant in path (e.g., baseline/2026-01-28__15-21-58/task_id/result.json)
            # The agent name would be the first part after the experiment directory
            if len(parts) >= 3:
                # Check if first part looks like an agent variant name (not a timestamp or task_id)
                first_part = parts[0]
                # Agent variant names are typically short, lowercase, no underscores with double digits
                if (
                    not first_part.startswith("instance_")  # Not a task ID
                    and "__" not in first_part  # Not a timestamp like 2026-01-28__15-21-58
                    and not first_part[0].isdigit()  # Not starting with a digit
                ):
                    return first_part

            return None
        except (ValueError, IndexError):
            return None
    
    def get_experiment_stats(self, experiment_id: str) -> dict:
        """Get statistics for an experiment."""
        return self.db.get_stats(experiment_id)
    
    def get_experiment_results(self, experiment_id: str) -> list[dict]:
        """Get all results for an experiment."""
        return self.db.get_experiment_results(experiment_id)
