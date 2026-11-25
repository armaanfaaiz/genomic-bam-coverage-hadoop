#!/usr/bin/env python3
"""
Master Pipeline Runner for Final Year Project:
'Sampling-Guided Machine Learning-Based Adaptive Partitioning and Heterogeneity-Aware Scheduling
 for Exact BAM Coverage Computation on Hadoop'

Executes all 5 Steps:
- Step 1: Feature Extraction & Workload Prediction via ML (LPA-style)
- Step 2: Adaptive Partitioning to eliminate computational skew
- Step 3: Heterogeneity-Aware Worker Profiling (ANODE-style) & HLPT Scheduling
- Step 4: Exact Distributed BAM Coverage Calculation (PanDepth-style difference array)
- Step 5: Comprehensive Performance Benchmarking & Automated Figure Generation
"""

import os
import sys
import time

os.environ["LOKY_MAX_CPU_COUNT"] = "4"

# Ensure src is in python path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, "src"))

from data.generate_synthetic_data import generate_synthetic_dataset
from src.step1_workload_prediction.train_workload_model import run_training_pipeline
from src.step5_evaluation.benchmark_runner import BenchmarkRunner


def main():
    print("""
================================================================================
  GENOMIC BAM COVERAGE ON HETEROGENEOUS HADOOP
  Sampling-Guided ML Adaptive Partitioning & Heterogeneity-Aware Scheduling
================================================================================
    """)
    total_pipeline_start = time.time()

    sam_path = os.path.join(BASE_DIR, "data", "synthetic_alignments.sam")
    bed_path = os.path.join(BASE_DIR, "data", "test_regions.bed")
    config_path = os.path.join(BASE_DIR, "config", "default_config.yaml")
    model_path = os.path.join(BASE_DIR, "results", "workload_model.joblib")

    # Step 0: Data Preparation
    if not os.path.exists(sam_path) or not os.path.exists(bed_path):
        print("[*] Dataset not found. Generating high-fidelity synthetic BAM/SAM dataset with hotspot skew...")
        generate_synthetic_dataset(config_path=config_path, output_dir=os.path.join(BASE_DIR, "data"))
    else:
        print(f"[+] Using existing dataset: {sam_path}")

    # Step 1: Train & Evaluate Workload Prediction Models
    predictor, df_features = run_training_pipeline(
        sam_path=sam_path,
        bed_path=bed_path,
        config_path=config_path,
        output_model_path=model_path
    )

    # Step 2 to Step 5: Adaptive Partitioning, Scheduling, Simulation, Benchmarking & Plots
    runner = BenchmarkRunner(config_path=config_path)
    df_comparison, details = runner.run_full_benchmark(
        sam_path=sam_path,
        bed_path=bed_path,
        model_path=model_path
    )

    total_pipeline_time = time.time() - total_pipeline_start
    print("\n" + "="*70)
    print(f" PIPELINE COMPLETED SUCCESSFULLY IN {total_pipeline_time:.2f} SECONDS")
    print(f" Output Results and Figures saved in: {os.path.join(BASE_DIR, 'results')}")
    print("="*70)


if __name__ == "__main__":
    main()
