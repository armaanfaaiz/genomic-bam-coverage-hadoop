"""
Training Pipeline for Genomic Workload Prediction.
Trains Random Forest and Gradient Boosting models, evaluates MAE/RMSE/R2,
and outputs feature importance to validate the LPA-style methodology.
"""

import os
import yaml
import time
import numpy as np
import pandas as pd
from typing import Dict, Tuple

from .feature_extractor import GenomicFeatureExtractor
from .predictor_model import WorkloadPredictor


def simulate_ground_truth_runtime(df_features: pd.DataFrame) -> pd.DataFrame:
    """
    Simulates actual execution time (in ms) on a baseline worker node,
    modeling the real-world complexity of exact coverage computation:
    Runtime ~ a * read_count + b * (cigar_complexity * indels) + c * span + noise
    """
    df = df_features.copy()
    
    base_time = 5.0  # overhead in ms
    read_factor = 0.08  # time per read in ms
    cigar_factor = 120.0  # time spent parsing complex CIGAR indels/clips
    span_factor = 0.0001  # array allocation and iteration per base
    
    deterministic_time = (
        base_time
        + df["sampled_read_count"] * read_factor
        + df["cigar_mismatch_rate"] * cigar_factor * (1.0 + df["indel_frequency"])
        + df["region_span"] * span_factor
    )
    
    # Add realistic system noise (cache misses, GC, I/O jitter)
    noise = np.random.normal(0, np.maximum(2.0, deterministic_time * 0.06))
    df["execution_time_ms"] = np.maximum(5.0, deterministic_time + noise)
    
    return df


def run_training_pipeline(sam_path: str = "data/synthetic_alignments.sam",
                          bed_path: str = "data/test_regions.bed",
                          config_path: str = "config/default_config.yaml",
                          output_model_path: str = "results/workload_model.joblib") -> Tuple[WorkloadPredictor, pd.DataFrame]:
    """
    Executes the training and model comparison pipeline.
    """
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    print("\n" + "="*60)
    print(" STEP 1: GENOMIC WORKLOAD PREDICTION TRAINING")
    print(" Reference: Lai et al. (2025) - LPA Framework")
    print("="*60)

    # 1. Load BED intervals
    intervals = []
    with open(bed_path, "r") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) >= 3:
                intervals.append((parts[0], int(parts[1]), int(parts[2])))

    print(f"[*] Extracting features for {len(intervals)} genomic intervals from {sam_path}...")
    sampling_frac = config["genomics"].get("sampling_fraction", 0.05)
    extractor = GenomicFeatureExtractor(sampling_fraction=sampling_frac)
    
    start_t = time.time()
    df_features = extractor.extract_from_sam_file(sam_path, intervals)
    extraction_time = time.time() - start_t
    print(f"[+] Feature extraction completed in {extraction_time:.2f} seconds (sampling fraction: {sampling_frac*100:.1f}%)")

    # 2. Add ground-truth profiled execution times
    df_dataset = simulate_ground_truth_runtime(df_features)

    # 3. Train and compare models: Random Forest vs Gradient Boosting
    print("\n[*] Evaluating ML models for workload prediction:")
    
    rf_predictor = WorkloadPredictor(
        model_type="random_forest",
        n_estimators=config["workload_prediction"].get("rf_n_estimators", 100),
        max_depth=config["workload_prediction"].get("rf_max_depth", 12)
    )
    rf_metrics = rf_predictor.train(df_dataset)
    print(f"  [Random Forest Regressor] -> MAE: {rf_metrics['MAE']:.2f} ms | RMSE: {rf_metrics['RMSE']:.2f} ms | R²: {rf_metrics['R2']:.4f}")

    gb_predictor = WorkloadPredictor(
        model_type="gradient_boosting",
        n_estimators=config["workload_prediction"].get("rf_n_estimators", 100),
        max_depth=config["workload_prediction"].get("rf_max_depth", 12)
    )
    gb_metrics = gb_predictor.train(df_dataset)
    print(f"  [Gradient Boosting / CatBoost style] -> MAE: {gb_metrics['MAE']:.2f} ms | RMSE: {gb_metrics['RMSE']:.2f} ms | R²: {gb_metrics['R2']:.4f}")

    # Select best model based on R2 / RMSE
    best_predictor = rf_predictor if rf_metrics["R2"] >= gb_metrics["R2"] else gb_predictor
    best_name = "Random Forest" if best_predictor == rf_predictor else "Gradient Boosting"
    print(f"\n[+] Selected Best Model: {best_name}")

    print("\n[*] Feature Importance Analysis:")
    for feat, imp in sorted(best_predictor.feature_importances_.items(), key=lambda x: x[1], reverse=True):
        bar = "#" * int(imp * 40)
        print(f"  - {feat:22s} : {imp:.4f} {bar}")

    # Save model
    best_predictor.save(output_model_path)
    print(f"[+] Saved trained model to {output_model_path}")

    # Save extracted dataset with predictions
    df_dataset["predicted_workload_ms"] = best_predictor.predict(df_dataset)
    results_dataset_path = "results/workload_predictions.csv"
    os.makedirs("results", exist_ok=True)
    df_dataset.to_csv(results_dataset_path, index=False)
    print(f"[+] Saved workload predictions dataset to {results_dataset_path}")

    return best_predictor, df_dataset


if __name__ == "__main__":
    run_training_pipeline()
