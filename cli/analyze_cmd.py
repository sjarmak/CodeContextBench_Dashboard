"""Analysis commands for the CLI."""

import json
from pathlib import Path
from src.ingest.database import MetricsDatabase
from src.analysis.comparator import ExperimentComparator
from src.analysis.failure_analyzer import FailureAnalyzer
from src.analysis.ir_analyzer import IRAnalyzer
from src.analysis.recommendation_engine import RecommendationEngine
from src.analysis.statistical_analyzer import StatisticalAnalyzer


def cmd_analyze_compare(args):
    """Compare agents in an experiment."""
    from pathlib import Path
    
    project_root = Path(__file__).parent.parent
    db_path = project_root / "data" / "metrics.db"
    
    if not db_path.exists():
        print(f"Error: Database not found: {db_path}")
        return 1
    
    db = MetricsDatabase(db_path)
    comparator = ExperimentComparator(db)
    
    try:
        result = comparator.compare_experiment(
            args.experiment_id,
            baseline_agent=args.baseline,
        )
        
        print(f"\n✓ Comparison Results for {args.experiment_id}\n")
        print(f"Baseline Agent: {result.baseline_agent}")
        print(f"Variant Agents: {', '.join(result.variant_agents)}")
        print(f"\nBest Agent: {result.best_agent}")
        print(f"Worst Agent: {result.worst_agent}")
        
        print(f"\nAgent Metrics:")
        for agent_name, metrics in result.agent_metrics.items():
            print(f"\n  {agent_name}:")
            print(f"    Pass Rate: {metrics.pass_rate:.1%}")
            print(f"    Avg Duration: {metrics.avg_duration_seconds:.1f}s")
            print(f"    Avg MCP Calls: {metrics.avg_mcp_calls:.1f}")
            print(f"    Avg Deep Search Calls: {metrics.avg_deep_search_calls:.1f}")
        
        # Save detailed results
        output_file = project_root / "artifacts" / f"comparison_{args.experiment_id}.json"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, "w") as f:
            json.dump(result.to_dict(), f, indent=2)
        
        print(f"\n✓ Detailed results saved to {output_file}")
        
        return 0
    
    except Exception as e:
        print(f"Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def cmd_analyze_failures(args):
    """Analyze failure patterns in an experiment."""
    from pathlib import Path
    
    project_root = Path(__file__).parent.parent
    db_path = project_root / "data" / "metrics.db"
    
    if not db_path.exists():
        print(f"Error: Database not found: {db_path}")
        return 1
    
    db = MetricsDatabase(db_path)
    analyzer = FailureAnalyzer(db)
    
    try:
        result = analyzer.analyze_failures(
            args.experiment_id,
            agent_name=args.agent,
        )
        
        print(f"\n✓ Failure Analysis for {result.agent_name}\n")
        print(f"Total Failures: {result.total_failures}/{result.total_tasks}")
        print(f"Failure Rate: {result.failure_rate:.1%}")
        
        if result.failure_rate_vs_baseline is not None:
            baseline_str = f"  vs Baseline: {result.failure_rate_vs_baseline:+.1%}"
            worse_str = " (WORSE)" if result.is_worse_than_baseline else ""
            print(f"{baseline_str}{worse_str}")
        
        if result.patterns:
            print(f"\nDetected Patterns ({len(result.patterns)}):")
            for pattern in result.patterns:
                print(f"\n  • {pattern.pattern_name}")
                print(f"    Frequency: {pattern.frequency}")
                print(f"    Confidence: {pattern.confidence:.1%}")
                print(f"    Fix: {pattern.suggested_fix}")
        
        if result.top_failing_categories:
            print(f"\nTop Failing Categories:")
            for category, count in result.top_failing_categories[:3]:
                print(f"  • {category}: {count} failures")
        
        if result.top_failing_difficulties:
            print(f"\nTop Failing Difficulties:")
            for difficulty, count in result.top_failing_difficulties[:3]:
                print(f"  • {difficulty}: {count} failures")
        
        # Save detailed results
        output_file = project_root / "artifacts" / f"failures_{args.experiment_id}_{result.agent_name}.json"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, "w") as f:
            json.dump(result.to_dict(), f, indent=2)
        
        print(f"\n✓ Detailed results saved to {output_file}")
        
        return 0
    
    except Exception as e:
        print(f"Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def cmd_analyze_ir(args):
    """Analyze IR metrics in an experiment."""
    from pathlib import Path
    
    project_root = Path(__file__).parent.parent
    db_path = project_root / "data" / "metrics.db"
    
    if not db_path.exists():
        print(f"Error: Database not found: {db_path}")
        return 1
    
    db = MetricsDatabase(db_path)
    analyzer = IRAnalyzer(db)
    
    try:
        result = analyzer.analyze_experiment(
            args.experiment_id,
            baseline_agent=args.baseline,
        )
        
        print(f"\n✓ IR Analysis Results for {args.experiment_id}\n")
        print(f"Best MRR Agent: {result.best_mrr_agent}")
        print(f"Best Recall Agent: {result.best_recall_agent}")
        print(f"Most Efficient Agent: {result.most_efficient_agent}")
        
        print(f"\nIR Metrics by Agent:")
        for agent_name, metrics in result.agent_metrics.items():
            print(f"\n  {agent_name}:")
            print(f"    MRR: {metrics.mrr:.3f}")
            print(f"    Precision@10: {metrics.precision_at_10:.3f}")
            print(f"    Recall@10: {metrics.recall_at_10:.3f}")
            print(f"    NDCG@10: {metrics.ndcg_at_10:.3f}")
            print(f"    Context Efficiency: {metrics.context_efficiency:.3f}")
        
        # Save detailed results
        output_file = project_root / "artifacts" / f"ir_analysis_{args.experiment_id}.json"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, "w") as f:
            json.dump(result.to_dict(), f, indent=2)
        
        print(f"\n✓ Detailed results saved to {output_file}")
        
        return 0
    
    except Exception as e:
        print(f"Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def cmd_analyze_statistical(args):
    """Perform statistical significance testing on an experiment."""
    from pathlib import Path
    
    project_root = Path(__file__).parent.parent
    db_path = project_root / "data" / "metrics.db"
    
    if not db_path.exists():
        print(f"Error: Database not found: {db_path}")
        return 1
    
    db = MetricsDatabase(db_path)
    analyzer = StatisticalAnalyzer(db)
    
    try:
        result = analyzer.analyze_comparison(
            args.experiment_id,
            baseline_agent=args.baseline,
            confidence_level=args.confidence,
        )
        
        print(f"\n✓ Statistical Analysis for {args.experiment_id}\n")
        print(f"Baseline Agent: {result.baseline_agent}")
        print(f"Variant Agents: {', '.join(result.variant_agents)}")
        print(f"\nStatistical Power: {result.power_assessment.title()}")
        print(f"Total Tests: {result.total_tests}")
        print(f"Significant Results: {result.significant_tests}/{result.total_tests}")
        
        if result.significant_metrics:
            print(f"\n✓ Significant Metrics ({len(result.significant_metrics)}):")
            for metric in result.significant_metrics:
                tests = result.tests.get(metric, [])
                for test in tests:
                    print(f"  • {test.metric_name}: {test.interpretation}")
                    print(f"    Effect size ({test.effect_size_name}): {test.effect_size:.3f}")
        
        if result.non_significant_metrics:
            print(f"\n→ Non-Significant Metrics ({len(result.non_significant_metrics)}):")
            for metric in result.non_significant_metrics[:5]:
                tests = result.tests.get(metric, [])
                for test in tests:
                    print(f"  • {test.metric_name}: p={test.p_value:.4f}")
        
        # Save detailed results
        output_file = project_root / "artifacts" / f"statistical_{args.experiment_id}.json"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, "w") as f:
            json.dump(result.to_dict(), f, indent=2)
        
        print(f"\n✓ Detailed results saved to {output_file}")
        
        return 0
    
    except Exception as e:
        print(f"Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def cmd_analyze_timeseries(args):
    """Perform time-series analysis on experiment metrics."""
    from pathlib import Path
    
    project_root = Path(__file__).parent.parent
    db_path = project_root / "data" / "metrics.db"
    
    if not db_path.exists():
        print(f"Error: Database not found: {db_path}")
        return 1
    
    db = MetricsDatabase(db_path)
    from src.analysis.time_series_analyzer import TimeSeriesAnalyzer, TrendDirection
    
    analyzer = TimeSeriesAnalyzer(db)
    
    try:
        # Parse experiment IDs from comma-separated list
        experiment_ids = args.experiments.split(",") if args.experiments else []
        
        if not experiment_ids:
            print("Error: Must provide experiment IDs (comma-separated)")
            return 1
        
        # Analyze multi-agent trends
        result = analyzer.analyze_multi_agent_trends(
            experiment_ids,
            agent_names=args.agents.split(",") if args.agents else None,
        )
        
        print(f"\n✓ Time-Series Analysis Results\n")
        print(f"Experiments: {', '.join(result.experiment_ids)}")
        print(f"Agents Analyzed: {', '.join(result.agent_names)}")
        
        if result.best_improving_metric:
            print(f"\n🚀 Best Improving: {result.best_improving_metric.metric_name}")
            print(f"   {result.best_improving_metric.interpretation}")
            print(f"   Change: {result.best_improving_metric.percent_change:+.1f}%")
        
        if result.worst_degrading_metric:
            print(f"\n⚠️  Worst Degrading: {result.worst_degrading_metric.metric_name}")
            print(f"   {result.worst_degrading_metric.interpretation}")
            print(f"   Change: {result.worst_degrading_metric.percent_change:+.1f}%")
        
        if result.most_stable_metric:
            print(f"\n→ Most Stable: {result.most_stable_metric.metric_name}")
            print(f"   {result.most_stable_metric.interpretation}")
        
        if result.total_anomalies > 0:
            print(f"\n⚠️  Anomalies Detected: {result.total_anomalies}")
            print(f"   Agents affected: {', '.join(result.agents_with_anomalies)}")
        
        # Detailed trends
        print(f"\nDetailed Trends by Metric:")
        for metric, agent_trends in result.trends.items():
            print(f"\n  {metric}:")
            for agent, trend in agent_trends.items():
                status = "✓" if trend.direction == TrendDirection.IMPROVING else "✗" if trend.direction == TrendDirection.DEGRADING else "→"
                print(f"    {status} {agent}: {trend.direction.value}")
                print(f"       Value: {trend.first_value:.3f} → {trend.last_value:.3f} ({trend.percent_change:+.1f}%)")
                print(f"       Confidence: {trend.confidence:.0%}")
        
        # Save detailed results
        output_file = project_root / "artifacts" / f"timeseries_{'_'.join(result.experiment_ids)}.json"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        import json
        with open(output_file, "w") as f:
            json.dump(result.to_dict(), f, indent=2)
        
        print(f"\n✓ Detailed results saved to {output_file}")
        
        return 0
    
    except Exception as e:
        print(f"Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def cmd_analyze_recommend(args):
    """Generate recommendations for an agent."""
    from pathlib import Path
    
    project_root = Path(__file__).parent.parent
    db_path = project_root / "data" / "metrics.db"
    
    if not db_path.exists():
        print(f"Error: Database not found: {db_path}")
        return 1
    
    db = MetricsDatabase(db_path)
    engine = RecommendationEngine()
    
    try:
        # Run all analyses
        comparator = ExperimentComparator(db)
        failure_analyzer = FailureAnalyzer(db)
        ir_analyzer = IRAnalyzer(db)
        
        comparison = comparator.compare_experiment(args.experiment_id)
        failures = failure_analyzer.analyze_failures(args.experiment_id, agent_name=args.agent)
        
        try:
            ir_analysis = ir_analyzer.analyze_experiment(args.experiment_id)
        except:
            ir_analysis = None
        
        # Generate plan
        plan = engine.generate_plan(
            args.experiment_id,
            args.agent,
            comparison_result=comparison,
            failure_analysis=failures,
            ir_analysis=ir_analysis,
        )
        
        print(f"\n✓ Recommendation Plan for {args.agent}\n")
        print(f"Total Issues Detected: {plan.total_issues_detected}")
        
        if plan.quick_wins:
            print(f"\n🚀 Quick Wins ({len(plan.quick_wins)}):")
            for rec in plan.quick_wins:
                print(f"  • {rec.title}")
                print(f"    {rec.description}")
        
        if plan.high_priority:
            print(f"\n⚠️  High Priority ({len(plan.high_priority)}):")
            for rec in plan.high_priority[:5]:
                print(f"  • {rec.title} (confidence: {rec.confidence:.1%})")
        
        if plan.medium_priority:
            print(f"\n→ Medium Priority ({len(plan.medium_priority)}):")
            for rec in plan.medium_priority[:3]:
                print(f"  • {rec.title}")
        
        # Save detailed results
        output_file = project_root / "artifacts" / f"recommendations_{args.experiment_id}_{args.agent}.json"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, "w") as f:
            json.dump(plan.to_dict(), f, indent=2)
        
        print(f"\n✓ Detailed plan saved to {output_file}")
        
        return 0
    
    except Exception as e:
        print(f"Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1
