"""
Sampling-Guided Machine Learning-Based Adaptive Partitioner.
Inspired by Lai et al. (2025) (LPA - Learning-based Parallel Acceleration).

Dynamically splits computationally expensive genomic regions into smaller sub-blocks
based on predicted workload, maintaining minimum and maximum interval bounds.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple


class AdaptivePartitioner:
    def __init__(self,
                 split_threshold_percentile: float = 75.0,
                 min_partition_size: int = 20000,
                 max_partition_size: int = 250000,
                 max_splits_per_region: int = 4):
        """
        :param split_threshold_percentile: Percentile of predicted workload above which regions are split
        :param min_partition_size: Minimum allowed partition size in bp (avoids task over-fragmentation)
        :param max_partition_size: Maximum allowed partition size in bp
        :param max_splits_per_region: Maximum number of sub-partitions a heavy region can be divided into
        """
        self.split_threshold_percentile = split_threshold_percentile
        self.min_partition_size = min_partition_size
        self.max_partition_size = max_partition_size
        self.max_splits_per_region = max_splits_per_region

    def partition(self,
                  df_workloads: pd.DataFrame,
                  workload_col: str = "predicted_workload_ms") -> pd.DataFrame:
        """
        Takes initial regions with predicted workloads and produces adaptively balanced partitions.
        """
        if workload_col not in df_workloads.columns:
            raise ValueError(f"Column '{workload_col}' not found in workload DataFrame.")

        # Determine threshold based on percentile
        threshold = np.percentile(df_workloads[workload_col], self.split_threshold_percentile)
        target_workload = np.median(df_workloads[workload_col])

        adaptive_records = []
        part_counter = 0

        for _, row in df_workloads.iterrows():
            chrom = str(row["chrom"])
            start = int(row["start"])
            end = int(row["end"])
            span = end - start
            workload = float(row[workload_col])

            # Condition for splitting:
            # 1. Workload meets or exceeds threshold AND
            # 2. Region span is at least 2 * min_partition_size
            if workload >= threshold and span >= (2 * self.min_partition_size):
                # Calculate number of splits proportional to excess workload
                k_splits = int(np.clip(
                    np.ceil(workload / max(1.0, target_workload)),
                    2,
                    self.max_splits_per_region
                ))

                # Ensure each sub-partition is at least min_partition_size
                k_splits = min(k_splits, span // self.min_partition_size)
                k_splits = max(1, k_splits)

                if k_splits > 1:
                    sub_len = span // k_splits
                    sub_workload = workload / k_splits

                    for i in range(k_splits):
                        sub_start = start + i * sub_len
                        sub_end = (start + (i + 1) * sub_len) if i < k_splits - 1 else end
                        adaptive_records.append({
                            "partition_id": f"adapt_{part_counter:04d}",
                            "parent_region": f"{chrom}:{start}-{end}",
                            "chrom": chrom,
                            "start": sub_start,
                            "end": sub_end,
                            "span": sub_end - sub_start,
                            "predicted_workload_ms": round(sub_workload, 2),
                            "was_split": True,
                            "split_factor": k_splits,
                            "type": "adaptive"
                        })
                        part_counter += 1
                    continue

            # If not split, preserve region
            adaptive_records.append({
                "partition_id": f"adapt_{part_counter:04d}",
                "parent_region": f"{chrom}:{start}-{end}",
                "chrom": chrom,
                "start": start,
                "end": end,
                "span": span,
                "predicted_workload_ms": round(workload, 2),
                "was_split": False,
                "split_factor": 1,
                "type": "adaptive"
            })
            part_counter += 1

        df_adaptive = pd.DataFrame(adaptive_records)
        return df_adaptive

    def compute_partition_balance_metrics(self,
                                          df_static: pd.DataFrame,
                                          df_adaptive: pd.DataFrame,
                                          workload_col: str = "predicted_workload_ms") -> Dict[str, float]:
        """
        Computes skew and balance comparison metrics between static and adaptive partitions.
        """
        static_loads = df_static[workload_col].values
        adaptive_loads = df_adaptive[workload_col].values

        static_std = float(np.std(static_loads))
        adaptive_std = float(np.std(adaptive_loads))

        static_max = float(np.max(static_loads))
        adaptive_max = float(np.max(adaptive_loads))

        # Coefficient of Variation (CV = std / mean)
        static_cv = static_std / float(np.mean(static_loads))
        adaptive_cv = adaptive_std / float(np.mean(adaptive_loads))

        skew_reduction_pct = ((static_max - adaptive_max) / static_max) * 100.0
        cv_reduction_pct = ((static_cv - adaptive_cv) / static_cv) * 100.0

        return {
            "static_partitions_count": len(df_static),
            "adaptive_partitions_count": len(df_adaptive),
            "static_max_workload_ms": round(static_max, 2),
            "adaptive_max_workload_ms": round(adaptive_max, 2),
            "static_load_std_ms": round(static_std, 2),
            "adaptive_load_std_ms": round(adaptive_std, 2),
            "static_load_cv": round(static_cv, 4),
            "adaptive_load_cv": round(adaptive_cv, 4),
            "peak_workload_reduction_pct": round(skew_reduction_pct, 2),
            "load_variance_reduction_pct": round(cv_reduction_pct, 2)
        }
