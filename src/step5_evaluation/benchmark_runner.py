"""
Benchmark Runner for Comparative Performance Evaluation.
Evaluates the 4 core configurations:
1. Baseline: Static Partitioning + FIFO Scheduling
2. Static Partitioning + HLPT Scheduling
3. Adaptive Partitioning + FIFO Scheduling
4. Proposed Framework: ML Adaptive Partitioning + HLPT Scheduling

Executes simulations, verifies exact correctness, measures speedup and straggler mitigation,
and generates publication-ready figures.
"""

import os
import time
import yaml
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple

from ..step1_workload_prediction.feature_extractor import GenomicFeatureExtractor
from ..step1_workload_prediction.predictor_model import WorkloadPredictor
from ..step2_adaptive_partitioning.static_partitioner import StaticPartitioner
from ..step2_adaptive_partitioning.adaptive_partitioner import AdaptivePartitioner
from ..step3_heterogeneity_scheduling.worker_profiler import WorkerProfiler
from ..step3_heterogeneity_scheduling.hlpt_scheduler import HLPTScheduler
from ..step4_mapreduce_coverage.exact_coverage_engine import ExactCoverageEngine
from ..step4_mapreduce_coverage.distributed_simulator import HeterogeneousClusterSimulator
from .metrics_calculator import MetricsCalculator
from .visualizer import ResearchVisualizer


class BenchmarkRunner:
    def __init__(self, config_path: str = "config/default_config.yaml"):
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)

        self.chrom = self.config["genomics"]["chrom"]
        self.region_len = self.config["genomics"]["region_length"]
        self.chunk_size = self.config["genomics"]["default_static_chunk_size"]
        self.min_part_size = self.config["genomics"]["min_partition_size"]
        self.max_part_size = self.config["genomics"]["max_partition_size"]

        # Worker profiles
        self.profiler = WorkerProfiler()
        self.worker_profiles = self.profiler.profile_from_cluster_config(
            self.config["cluster_heterogeneity"]["workers"]
        )

        self.visualizer = ResearchVisualizer(self.config["evaluation"].get("output_dir", "results"))

    def run_full_benchmark(self,
                           sam_path: str = "data/synthetic_alignments.sam",
                           bed_path: str = "data/test_regions.bed",
                           model_path: str = "results/workload_model.joblib") -> Tuple[pd.DataFrame, Dict]:
        """
        Executes end-to-end benchmarking across all 4 configurations.
        """
        print("\n" + "="*70)
        print(" STEP 5: COMPREHENSIVE PERFORMANCE EVALUATION & BENCHMARKING")
        print(" Comparing Proposed vs Static & Homogeneous Scheduling Baselines")
        print("="*70)

        # 1. Load SAM reads into memory for fast simulation
        print(f"[*] Reading alignments from {sam_path}...")
        reads_data = []
        with open(sam_path, "r") as f:
            for line in f:
                if line.startswith("@"):
                    continue
                parts = line.strip().split("\t")
                if len(parts) >= 11:
                    reads_data.append({
                        "chrom": parts[2],
                        "pos": int(parts[3]),
                        "mapq": int(parts[4]),
                        "cigar": parts[5],
                        "seq": parts[9],
                        "flag": int(parts[1])
                    })
        print(f"[+] Loaded {len(reads_data):,} alignments.")

        # 2. Compute Sequential Ground-Truth Exact Coverage (Reference)
        print("[*] Computing sequential ground-truth coverage for validation...")
        t_seq_start = time.perf_counter()
        engine = ExactCoverageEngine()
        ref_depths, _, ref_metrics = engine.compute_exact_interval_coverage(reads_data, 0, self.region_len)
        seq_time = time.perf_counter() - t_seq_start
        print(f"[+] Reference coverage computed in {seq_time:.2f}s (Mean Depth: {ref_metrics['mean_coverage_depth']}x)")

        # 3. Load or train workload predictor
        if os.path.exists(model_path):
            predictor = WorkloadPredictor.load(model_path)
            print(f"[+] Loaded trained workload model from {model_path}")
        else:
            raise FileNotFoundError(f"Model file {model_path} not found. Run Step 1 first.")

        # 4. Generate Static Partitions
        print("\n[*] Generating Partitions:")
        static_p = StaticPartitioner(chunk_size=self.chunk_size)
        df_static = static_p.partition_to_dataframe(self.chrom, 0, self.region_len)

        # Feature extraction on static partitions to get predicted workload
        extractor = GenomicFeatureExtractor(sampling_fraction=self.config["genomics"]["sampling_fraction"])
        intervals_static = [(r["chrom"], r["start"], r["end"]) for _, r in df_static.iterrows()]
        df_feats_static = extractor.extract_from_sam_file(sam_path, intervals_static)
        df_static["predicted_workload_ms"] = predictor.predict(df_feats_static)
        print(f"  - Static Partitions: {len(df_static)} blocks of {self.chunk_size:,} bp")

        # 5. Generate Adaptive Partitions using LPA concept
        adaptive_p = AdaptivePartitioner(
            split_threshold_percentile=self.config["adaptive_partitioning"]["split_threshold_percentile"],
            min_partition_size=self.min_part_size,
            max_partition_size=self.max_part_size
        )
        df_adaptive = adaptive_p.partition(df_static, workload_col="predicted_workload_ms")
        part_balance_metrics = adaptive_p.compute_partition_balance_metrics(df_static, df_adaptive)
        print(f"  - Adaptive Partitions: {len(df_adaptive)} blocks (Skew reduction: {part_balance_metrics['peak_workload_reduction_pct']}%)")

        # Prepare task dictionaries
        tasks_static = df_static.to_dict(orient="records")
        tasks_adaptive = df_adaptive.to_dict(orient="records")

        # 6. Execute Simulations for 4 Scenarios
        scenarios = [
            ("1. Baseline (Static + FIFO)", tasks_static, "FIFO", 0.0),
            ("2. Static + HLPT", tasks_static, "HLPT", 12.0),
            ("3. Adaptive + FIFO", tasks_adaptive, "FIFO", 25.0),
            ("4. Proposed (Adaptive + HLPT)", tasks_adaptive, "HLPT", 37.0)
        ]

        simulator = HeterogeneousClusterSimulator(self.worker_profiles)
        scenario_task_logs = {}
        benchmark_metrics_list = []
        assembled_coverages = {}

        for sc_name, task_list, algo, overhead in scenarios:
            print(f"\n[*] Running Scenario: {sc_name}...")
            scheduler = HLPTScheduler(self.worker_profiles, algorithm=algo)
            scheduled = scheduler.schedule(task_list)

            df_exec, assembled_cov, job_metrics = simulator.run_simulation(
                scheduled, reads_data, self.region_len, chrom=self.chrom
            )

            # Validate 100% exact correctness against ground-truth
            is_correct = ExactCoverageEngine.verify_correctness(ref_depths, assembled_cov)
            if not is_correct:
                # Find number of mismatched bases
                mismatches = np.sum(ref_depths != assembled_cov)
                print(f"  [!] Correctness Warning: {mismatches} bases differ from reference!")
            else:
                print(f"  [OK] Exact Coverage Correctness: 100.0% MATCH with Reference!")

            sc_metrics = MetricsCalculator.calculate_scenario_metrics(
                sc_name, df_exec, self.worker_profiles, overhead_ms=overhead
            )
            sc_metrics["exact_correctness"] = is_correct

            benchmark_metrics_list.append(sc_metrics)
            scenario_task_logs[sc_name] = df_exec
            assembled_coverages[sc_name] = assembled_cov

            print(f"      Makespan: {sc_metrics['makespan_sec']:.2f}s | Straggler: {sc_metrics['straggler_duration_ms']/1000.0:.2f}s | Utilization: {sc_metrics['cluster_utilization_pct']}%")

        # 7. Comparative Performance DataFrame
        df_comparison = MetricsCalculator.compare_against_baseline(benchmark_metrics_list)
        print("\n" + "="*70)
        print(" FINAL EXPERIMENTAL RESULTS SUMMARY")
        print("="*70)
        print(df_comparison.to_string(index=False))

        # Save results to CSV
        os.makedirs("results", exist_ok=True)
        comparison_csv_path = "results/benchmark_comparison.csv"
        df_comparison.to_csv(comparison_csv_path, index=False)
        print(f"\n[+] Saved benchmark summary to {comparison_csv_path}")

        # 8. Generate Research Visualizations
        print("\n[*] Generating Publication Figures...")
        self.visualizer.plot_makespan_and_speedup(df_comparison)
        self.visualizer.plot_straggler_mitigation(scenario_task_logs)
        self.visualizer.plot_worker_timeline_gantt(
            scenario_task_logs["1. Baseline (Static + FIFO)"],
            scenario_task_logs["4. Proposed (Adaptive + HLPT)"]
        )
        pred_csv_path = "results/workload_predictions.csv"
        df_pred_plot = pd.read_csv(pred_csv_path) if os.path.exists(pred_csv_path) else df_static
        self.visualizer.plot_ml_accuracy(
            df_pred_plot,
            predictor.feature_importances_,
            predictor.evaluation_metrics
        )
        self.visualizer.plot_coverage_correctness(
            ref_depths,
            assembled_coverages["4. Proposed (Adaptive + HLPT)"]
        )

        return df_comparison, {
            "metrics": benchmark_metrics_list,
            "partition_balance": part_balance_metrics,
            "model_metrics": predictor.evaluation_metrics
        }


if __name__ == "__main__":
    runner = BenchmarkRunner()
    runner.run_full_benchmark()
