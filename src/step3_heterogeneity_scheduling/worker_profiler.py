"""
Worker Profiler and Node Capability Estimator.
Inspired by Verma, Kumar and Naik (2025) (ANODE - Adaptive Node-Oriented Data Placement).

Analyzes historical execution logs of Hadoop worker nodes and calculates:
- Task Execution Duration per workload unit
- Processing Rate (R_i)
- Normalized Duration Time (NDT_i)
- Node Capacity Factor (C_i)
"""

import os
import json
import numpy as np
import pandas as pd
from typing import Dict, List, Optional


class WorkerProfiler:
    def __init__(self):
        self.node_profiles: Dict[str, Dict] = {}

    def profile_from_execution_logs(self, log_records: List[Dict]) -> Dict[str, Dict]:
        """
        Parses historical task execution records:
        Each record: {"node_id": str, "workload_units": float, "duration_ms": float}
        Computes NDT and capacity factors.
        """
        df = pd.DataFrame(log_records)
        if df.empty or "node_id" not in df.columns:
            raise ValueError("Log records must contain 'node_id', 'workload_units', and 'duration_ms'.")

        # Rate per task: units processed per millisecond
        df["rate"] = df["workload_units"] / np.maximum(1.0, df["duration_ms"])

        # Mean rate per node R_i
        node_rates = df.groupby("node_id")["rate"].mean().to_dict()
        node_counts = df.groupby("node_id")["rate"].count().to_dict()

        # Mean cluster rate R_avg
        cluster_avg_rate = float(np.mean(list(node_rates.values())))

        self.node_profiles = {}
        for node_id, r_i in node_rates.items():
            # Capacity factor C_i = R_i / R_avg
            capacity_factor = float(r_i / cluster_avg_rate) if cluster_avg_rate > 0 else 1.0
            # Normalized Duration Time NDT_i = 1 / C_i
            ndt = 1.0 / capacity_factor if capacity_factor > 0 else 1.0

            self.node_profiles[node_id] = {
                "node_id": node_id,
                "task_count": node_counts[node_id],
                "avg_processing_rate": round(r_i, 6),
                "capacity_factor": round(capacity_factor, 4),
                "normalized_duration_time_ndt": round(ndt, 4)
            }

        return self.node_profiles

    def profile_from_cluster_config(self, workers_cfg: List[Dict]) -> Dict[str, Dict]:
        """
        Initializes worker profiles directly from cluster configuration.
        """
        raw_capacities = {w["id"]: float(w.get("capacity_factor", 1.0)) for w in workers_cfg}
        mean_cap = float(np.mean(list(raw_capacities.values())))

        self.node_profiles = {}
        for w in workers_cfg:
            nid = w["id"]
            norm_cap = raw_capacities[nid] / mean_cap if mean_cap > 0 else 1.0
            ndt = 1.0 / norm_cap if norm_cap > 0 else 1.0
            cores = w.get("cores", 4)
            self.node_profiles[nid] = {
                "node_id": nid,
                "cores": cores,
                "capacity_factor": round(norm_cap, 4),
                "normalized_duration_time_ndt": round(ndt, 4),
                "avg_processing_rate": round(norm_cap, 4)
            }
        return self.node_profiles

    def get_capacity(self, node_id: str) -> float:
        """
        Returns capacity factor for the given worker node.
        """
        if node_id in self.node_profiles:
            return self.node_profiles[node_id]["capacity_factor"]
        return 1.0

    def get_ndt(self, node_id: str) -> float:
        """
        Returns Normalized Duration Time for the given worker node.
        """
        if node_id in self.node_profiles:
            return self.node_profiles[node_id]["normalized_duration_time_ndt"]
        return 1.0
