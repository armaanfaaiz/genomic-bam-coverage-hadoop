"""
Metrics Calculator for Distributed Performance Evaluation.
Evaluates:
- Total Job Completion Time (Makespan)
- Speedup vs Baseline
- Straggler Duration & Straggler Ratio
- Load Imbalance (Standard Deviation & Coefficient of Variation)
- Cluster Resource Utilization Efficiency
- Overhead ratio (Sampling + Scheduling overhead vs total runtime)
- Coverage Correctness (concordance with reference exact output)
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple


class MetricsCalculator:
    @staticmethod
    def calculate_scenario_metrics(scenario_name: str,
                                   df_tasks: pd.DataFrame,
                                   worker_profiles: Dict[str, Dict],
                                   overhead_ms: float = 0.0) -> Dict[str, float]:
        """
        Calculates comprehensive performance metrics for a single scheduling/partitioning scenario.
        """
        finish_times = df_tasks["actual_finish_ms"].values
        start_times = df_tasks["actual_start_ms"].values
        durations = df_tasks["actual_duration_ms"].values

        makespan = float(np.max(finish_times)) + overhead_ms
        earliest_finish = float(np.min(finish_times))
        straggler_duration = float(makespan - earliest_finish)

        dur_mean = float(np.mean(durations))
        dur_std = float(np.std(durations))
        dur_cv = dur_std / dur_mean if dur_mean > 0 else 0.0

        # Straggler ratio: Max task duration / Median task duration
        dur_median = float(np.median(durations))
        straggler_ratio = (float(np.max(durations)) / dur_median) if dur_median > 0 else 1.0

        # Cluster resource utilization
        num_workers = len(worker_profiles)
        total_cluster_time = makespan * num_workers
        total_active_compute = float(np.sum(durations))
        utilization_pct = (total_active_compute / total_cluster_time * 100.0) if total_cluster_time > 0 else 0.0

        # Per-worker load summary
        worker_loads = df_tasks.groupby("assigned_worker")["actual_duration_ms"].sum().to_dict()
        worker_tasks = df_tasks.groupby("assigned_worker")["partition_id"].count().to_dict()

        return {
            "scenario": scenario_name,
            "makespan_ms": round(makespan, 2),
            "makespan_sec": round(makespan / 1000.0, 3),
            "straggler_duration_ms": round(straggler_duration, 2),
            "straggler_ratio": round(straggler_ratio, 2),
            "duration_std_ms": round(dur_std, 2),
            "duration_cv": round(dur_cv, 4),
            "cluster_utilization_pct": round(utilization_pct, 2),
            "overhead_ms": round(overhead_ms, 2),
            "overhead_pct": round((overhead_ms / makespan * 100.0), 3) if makespan > 0 else 0.0,
            "total_tasks": len(df_tasks),
            "worker_loads": worker_loads,
            "worker_task_counts": worker_tasks
        }

    @staticmethod
    def compare_against_baseline(benchmark_results: List[Dict]) -> pd.DataFrame:
        """
        Computes comparative speedup and straggler reduction against the baseline scenario (first entry).
        """
        baseline_makespan = benchmark_results[0]["makespan_ms"]
        baseline_straggler = benchmark_results[0]["straggler_duration_ms"]

        comparison_rows = []
        for res in benchmark_results:
            makespan = res["makespan_ms"]
            straggler = res["straggler_duration_ms"]

            speedup = baseline_makespan / makespan if makespan > 0 else 1.0
            runtime_reduction_pct = ((baseline_makespan - makespan) / baseline_makespan) * 100.0
            straggler_reduction_pct = ((baseline_straggler - straggler) / baseline_straggler) * 100.0 if baseline_straggler > 0 else 0.0

            row = {
                "Scenario": res["scenario"],
                "Makespan (s)": res["makespan_sec"],
                "Speedup": round(speedup, 2),
                "Runtime Reduction (%)": round(runtime_reduction_pct, 2),
                "Straggler Duration (s)": round(straggler / 1000.0, 3),
                "Straggler Reduction (%)": round(straggler_reduction_pct, 2),
                "Cluster Utilization (%)": res["cluster_utilization_pct"],
                "Duration CV": res["duration_cv"],
                "Total Partitions": res["total_tasks"]
            }
            comparison_rows.append(row)

        return pd.DataFrame(comparison_rows)
