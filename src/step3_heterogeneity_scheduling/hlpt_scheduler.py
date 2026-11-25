"""
Heterogeneity-Aware Task Scheduler for Hadoop Workers.
Implements:
1. HLPT (Heterogeneous Longest Processing Time) - Proposed Strategy
2. Standard LPT (Homogeneous LPT)
3. FIFO (First-In, First-Out / Default Hadoop YARN baseline)
4. Round-Robin
"""

import heapq
from enum import Enum
from typing import Dict, List, Optional, Tuple
import pandas as pd


class SchedulingAlgorithm(Enum):
    HLPT = "HLPT"
    LPT = "LPT"
    FIFO = "FIFO"
    ROUND_ROBIN = "ROUND_ROBIN"


class HLPTScheduler:
    def __init__(self,
                 worker_profiles: Dict[str, Dict],
                 algorithm: str = "HLPT"):
        """
        :param worker_profiles: Dictionary of worker node profiles with capacity_factor and NDT
        :param algorithm: Scheduling strategy ("HLPT", "LPT", "FIFO", "ROUND_ROBIN")
        """
        self.worker_profiles = worker_profiles
        self.workers = list(worker_profiles.keys())
        self.algorithm = SchedulingAlgorithm[algorithm.upper()]

    def schedule(self, tasks: List[Dict]) -> List[Dict]:
        """
        Schedules a list of genomic partition tasks to worker nodes.
        Each task dict: {"partition_id": str, "predicted_workload_ms": float, ...}
        Returns list of task assignments with assigned worker, start time, finish time, and duration.
        """
        if self.algorithm == SchedulingAlgorithm.HLPT:
            return self._schedule_hlpt(tasks)
        elif self.algorithm == SchedulingAlgorithm.LPT:
            return self._schedule_lpt(tasks)
        elif self.algorithm == SchedulingAlgorithm.FIFO:
            return self._schedule_fifo(tasks)
        elif self.algorithm == SchedulingAlgorithm.ROUND_ROBIN:
            return self._schedule_round_robin(tasks)
        else:
            raise ValueError(f"Unsupported algorithm: {self.algorithm}")

    def _schedule_hlpt(self, tasks: List[Dict]) -> List[Dict]:
        """
        Heterogeneous Longest Processing Time (HLPT) scheduling:
        1. Sort tasks in descending order of predicted baseline workload.
        2. For each task, assign to the worker that yields the earliest completion time:
           Earliest Completion = argmin_i (Current_Load_i + Task_Workload / Capacity_i)
        """
        # Sort tasks descending by predicted workload (Longest tasks first)
        sorted_tasks = sorted(tasks, key=lambda t: t.get("predicted_workload_ms", 1.0), reverse=True)

        # Track worker loads and timeline: node_id -> current_load_time
        worker_loads = {w: 0.0 for w in self.workers}
        assignments = []

        for task in sorted_tasks:
            w_base = float(task.get("predicted_workload_ms", 10.0))

            best_worker = None
            min_completion_time = float("inf")

            for node_id in self.workers:
                capacity = self.worker_profiles[node_id].get("capacity_factor", 1.0)
                # Duration on this heterogeneous node
                node_duration = w_base / max(0.01, capacity)
                completion_time = worker_loads[node_id] + node_duration

                if completion_time < min_completion_time:
                    min_completion_time = completion_time
                    best_worker = node_id

            # Assign to best worker
            capacity = self.worker_profiles[best_worker].get("capacity_factor", 1.0)
            actual_duration = w_base / max(0.01, capacity)
            start_time = worker_loads[best_worker]
            finish_time = start_time + actual_duration
            worker_loads[best_worker] = finish_time

            assigned_task = dict(task)
            assigned_task.update({
                "assigned_worker": best_worker,
                "node_capacity_factor": capacity,
                "scheduled_start_time_ms": round(start_time, 2),
                "scheduled_finish_time_ms": round(finish_time, 2),
                "task_duration_ms": round(actual_duration, 2),
                "algorithm": "HLPT"
            })
            assignments.append(assigned_task)

        return assignments

    def _schedule_lpt(self, tasks: List[Dict]) -> List[Dict]:
        """
        Homogeneous LPT (assumes all workers are equal when making assignment decisions).
        """
        sorted_tasks = sorted(tasks, key=lambda t: t.get("predicted_workload_ms", 1.0), reverse=True)
        worker_loads = {w: 0.0 for w in self.workers}
        assignments = []

        for task in sorted_tasks:
            w_base = float(task.get("predicted_workload_ms", 10.0))
            # Pick worker with least current simulated time (ignoring capacity differences)
            best_worker = min(self.workers, key=lambda w: worker_loads[w])
            
            # But the actual duration depends on physical worker capacity!
            capacity = self.worker_profiles[best_worker].get("capacity_factor", 1.0)
            actual_duration = w_base / max(0.01, capacity)
            start_time = worker_loads[best_worker]
            finish_time = start_time + actual_duration
            worker_loads[best_worker] = finish_time

            assigned_task = dict(task)
            assigned_task.update({
                "assigned_worker": best_worker,
                "node_capacity_factor": capacity,
                "scheduled_start_time_ms": round(start_time, 2),
                "scheduled_finish_time_ms": round(finish_time, 2),
                "task_duration_ms": round(actual_duration, 2),
                "algorithm": "LPT"
            })
            assignments.append(assigned_task)

        return assignments

    def _schedule_fifo(self, tasks: List[Dict]) -> List[Dict]:
        """
        FIFO / First-In First-Out: Tasks assigned in order of genomic coordinates / arrival
        to whichever worker becomes available first.
        """
        worker_loads = {w: 0.0 for w in self.workers}
        assignments = []

        for task in tasks:
            w_base = float(task.get("predicted_workload_ms", 10.0))
            best_worker = min(self.workers, key=lambda w: worker_loads[w])

            capacity = self.worker_profiles[best_worker].get("capacity_factor", 1.0)
            actual_duration = w_base / max(0.01, capacity)
            start_time = worker_loads[best_worker]
            finish_time = start_time + actual_duration
            worker_loads[best_worker] = finish_time

            assigned_task = dict(task)
            assigned_task.update({
                "assigned_worker": best_worker,
                "node_capacity_factor": capacity,
                "scheduled_start_time_ms": round(start_time, 2),
                "scheduled_finish_time_ms": round(finish_time, 2),
                "task_duration_ms": round(actual_duration, 2),
                "algorithm": "FIFO"
            })
            assignments.append(assigned_task)

        return assignments

    def _schedule_round_robin(self, tasks: List[Dict]) -> List[Dict]:
        """
        Round-Robin: tasks distributed evenly in cyclic order across workers.
        """
        worker_loads = {w: 0.0 for w in self.workers}
        assignments = []
        n_workers = len(self.workers)

        for idx, task in enumerate(tasks):
            assigned_worker = self.workers[idx % n_workers]
            w_base = float(task.get("predicted_workload_ms", 10.0))

            capacity = self.worker_profiles[assigned_worker].get("capacity_factor", 1.0)
            actual_duration = w_base / max(0.01, capacity)
            start_time = worker_loads[assigned_worker]
            finish_time = start_time + actual_duration
            worker_loads[assigned_worker] = finish_time

            assigned_task = dict(task)
            assigned_task.update({
                "assigned_worker": assigned_worker,
                "node_capacity_factor": capacity,
                "scheduled_start_time_ms": round(start_time, 2),
                "scheduled_finish_time_ms": round(finish_time, 2),
                "task_duration_ms": round(actual_duration, 2),
                "algorithm": "ROUND_ROBIN"
            })
            assignments.append(assigned_task)

        return assignments
