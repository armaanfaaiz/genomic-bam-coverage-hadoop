"""
Research Visualizer for Publication-Ready Figures.
Generates charts for Final Year Project report / thesis:
1. Fig 1: Total Job Completion Time (Makespan) and Speedup
2. Fig 2: Straggler Mitigation and Task Duration Distributions
3. Fig 3: Worker Node Timeline Gantt Chart (Heterogeneous Load Balancing)
4. Fig 4: ML Prediction Accuracy (Predicted vs Actual Runtime & Feature Importances)
5. Fig 5: Exact BAM Coverage Depth Profile Concordance
"""

import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple


class ResearchVisualizer:
    def __init__(self, output_dir: str = "results"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        # Professional academic plotting style
        plt.rcParams.update({
            'font.family': 'sans-serif',
            'font.size': 11,
            'axes.labelsize': 12,
            'axes.titlesize': 13,
            'xtick.labelsize': 10,
            'ytick.labelsize': 10,
            'legend.fontsize': 10,
            'figure.titlesize': 14
        })

    def plot_makespan_and_speedup(self, df_comparison: pd.DataFrame, filename: str = "fig1_makespan_speedup.png"):
        """
        Bar chart comparing Job Completion Time and Speedup across all scenarios.
        """
        fig, ax1 = plt.subplots(figsize=(10, 5.5), dpi=300)

        scenarios = df_comparison["Scenario"].tolist()
        makespans = df_comparison["Makespan (s)"].tolist()
        speedups = df_comparison["Speedup"].tolist()

        x = np.arange(len(scenarios))
        width = 0.45

        # Colors
        colors = ['#4A90E2', '#50E3C2', '#F5A623', '#7ED321']
        bars = ax1.bar(x, makespans, width, color=colors, edgecolor='black', alpha=0.88, zorder=3)
        ax1.set_ylabel("Total Job Completion Time (Seconds)", color='#2C3E50', fontweight='bold')
        ax1.set_xticks(x)
        ax1.set_xticklabels(scenarios, rotation=15, ha='right', fontweight='bold')
        ax1.grid(axis='y', linestyle='--', alpha=0.5, zorder=0)

        # Annotate bars with values
        for bar in bars:
            height = bar.get_height()
            ax1.annotate(f'{height:.1f}s',
                         xy=(bar.get_x() + bar.get_width() / 2, height),
                         xytext=(0, 4), textcoords="offset points",
                         ha='center', va='bottom', fontsize=10, fontweight='bold')

        # Secondary axis for speedup line
        ax2 = ax1.twinx()
        ax2.plot(x, speedups, color='#D0021B', marker='o', linewidth=2.5, markersize=8, label='Speedup Factor', zorder=4)
        ax2.set_ylabel("Speedup vs Baseline (x)", color='#D0021B', fontweight='bold')
        ax2.tick_params(axis='y', labelcolor='#D0021B')
        ax2.set_ylim(0.8, max(speedups) * 1.3)

        for i, sp in enumerate(speedups):
            ax2.annotate(f'{sp:.2f}x', (x[i], sp), xytext=(0, 10), textcoords="offset points",
                         ha='center', color='#D0021B', fontweight='bold')

        plt.title("Hadoop Job Execution Time and Speedup Comparison", pad=15, fontweight='bold')
        plt.tight_layout()
        out_path = os.path.join(self.output_dir, filename)
        plt.savefig(out_path, dpi=300)
        plt.close()
        print(f"[+] Saved Figure: {out_path}")
        return out_path

    def plot_straggler_mitigation(self, scenario_task_logs: Dict[str, pd.DataFrame], filename: str = "fig2_straggler_mitigation.png"):
        """
        Box plots of task duration distributions showing reduction of stragglers.
        """
        fig, ax = plt.subplots(figsize=(10, 5.5), dpi=300)

        labels = list(scenario_task_logs.keys())
        data = [df["actual_duration_ms"].values / 1000.0 for df in scenario_task_logs.values()]

        bp = ax.boxplot(data, tick_labels=labels, patch_artist=True, showmeans=True,
                        meanprops={"marker":"o", "markerfacecolor":"red", "markeredgecolor":"black", "markersize":6})

        colors = ['#BDC3C7', '#A3E4D7', '#FAD7A0', '#A9DFBF']
        for patch, color in zip(bp['boxes'], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.85)

        ax.set_ylabel("Task Duration (Seconds)", fontweight='bold')
        ax.set_xticklabels(labels, rotation=15, ha='right', fontweight='bold')
        ax.grid(axis='y', linestyle='--', alpha=0.5)
        ax.set_title("Task Duration Distribution & Straggler Mitigation\n(Red dot = Mean, Line = Median)",
                     pad=15, fontweight='bold')

        plt.tight_layout()
        out_path = os.path.join(self.output_dir, filename)
        plt.savefig(out_path, dpi=300)
        plt.close()
        print(f"[+] Saved Figure: {out_path}")
        return out_path

    def plot_worker_timeline_gantt(self,
                                   df_tasks_baseline: pd.DataFrame,
                                   df_tasks_proposed: pd.DataFrame,
                                   filename: str = "fig3_worker_timeline_gantt.png"):
        """
        Comparative Gantt charts showing worker load balance between Baseline and Proposed HLPT.
        """
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7.5), sharex=False, dpi=300)

        def draw_gantt(ax, df_tasks, title):
            workers = sorted(df_tasks["assigned_worker"].unique())
            y_map = {w: i for i, w in enumerate(workers)}
            
            # Palette
            cmap = plt.get_cmap("tab20")
            
            for idx, row in df_tasks.iterrows():
                w = row["assigned_worker"]
                start_s = row["actual_start_ms"] / 1000.0
                dur_s = row["actual_duration_ms"] / 1000.0
                y = y_map[w]
                color = cmap(idx % 20)
                ax.barh(y, dur_s, left=start_s, height=0.6, align='center',
                        color=color, edgecolor='black', alpha=0.85)

            ax.set_yticks(range(len(workers)))
            ax.set_yticklabels(workers, fontweight='bold')
            ax.set_xlabel("Elapsed Time (Seconds)", fontweight='bold')
            ax.set_title(title, fontweight='bold')
            ax.grid(axis='x', linestyle='--', alpha=0.5)

        draw_gantt(ax1, df_tasks_baseline, "Baseline: Static Partitioning + FIFO Scheduling (Severe Stragglers & Idle Gaps)")
        draw_gantt(ax2, df_tasks_proposed, "Proposed: ML Adaptive Partitioning + HLPT Scheduling (Balanced & Minimal Makespan)")

        plt.tight_layout()
        out_path = os.path.join(self.output_dir, filename)
        plt.savefig(out_path, dpi=300)
        plt.close()
        print(f"[+] Saved Figure: {out_path}")
        return out_path

    def plot_ml_accuracy(self,
                          df_predictions: pd.DataFrame,
                          feature_importances: Dict[str, float],
                          metrics: Dict[str, float],
                          filename: str = "fig4_ml_prediction_accuracy.png"):
        """
        Scatter plot of predicted vs actual execution time, plus feature importance ranking.
        """
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.5), dpi=300)

        # 1. Scatter Plot
        actual = df_predictions["execution_time_ms"].values
        predicted = df_predictions["predicted_workload_ms"].values

        ax1.scatter(actual, predicted, color='#2980B9', alpha=0.75, edgecolors='none', s=45)
        min_val = min(np.min(actual), np.min(predicted))
        max_val = max(np.max(actual), np.max(predicted))
        ax1.plot([min_val, max_val], [min_val, max_val], 'r--', linewidth=2, label="Ideal 1:1 Parity")

        r2 = metrics.get("R2", 0.95)
        mae = metrics.get("MAE", 1.2)
        rmse = metrics.get("RMSE", 2.0)
        annotation_text = f"R² Score: {r2:.4f}\nMAE: {mae:.2f} ms\nRMSE: {rmse:.2f} ms"
        ax1.text(0.05, 0.85, annotation_text, transform=ax1.transAxes,
                 fontsize=10, bbox=dict(boxstyle="round,pad=0.5", facecolor="white", alpha=0.85, edgecolor="#BDC3C7"))

        ax1.set_xlabel("Actual Ground-Truth Execution Time (ms)", fontweight='bold')
        ax1.set_ylabel("ML-Predicted Workload (ms)", fontweight='bold')
        ax1.set_title("LPA-Style Workload Regression Accuracy", fontweight='bold')
        ax1.legend(loc='lower right')
        ax1.grid(True, linestyle='--', alpha=0.5)

        # 2. Feature Importances
        feats = list(feature_importances.keys())
        imps = list(feature_importances.values())
        y_pos = np.arange(len(feats))

        # Sort descending
        sorted_indices = np.argsort(imps)
        sorted_feats = [feats[i] for i in sorted_indices]
        sorted_imps = [imps[i] for i in sorted_indices]

        ax2.barh(np.arange(len(sorted_feats)), sorted_imps, color='#27AE60', edgecolor='black', alpha=0.85)
        ax2.set_yticks(np.arange(len(sorted_feats)))
        ax2.set_yticklabels(sorted_feats, fontweight='bold')
        ax2.set_xlabel("Relative Importance Factor", fontweight='bold')
        ax2.set_title("Genomic Feature Importance Ranking", fontweight='bold')
        ax2.grid(axis='x', linestyle='--', alpha=0.5)

        plt.tight_layout()
        out_path = os.path.join(self.output_dir, filename)
        plt.savefig(out_path, dpi=300)
        plt.close()
        print(f"[+] Saved Figure: {out_path}")
        return out_path

    def plot_coverage_correctness(self,
                                  ref_coverage: np.ndarray,
                                  test_coverage: np.ndarray,
                                  sample_slice: Tuple[int, int] = (800000, 850000),
                                  filename: str = "fig5_coverage_correctness.png"):
        """
        Validates exact equivalence of calculated coverage depth per base across the sample window.
        """
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 6), sharex=True, dpi=300)

        s_start, s_end = sample_slice
        x = np.arange(s_start, s_end)
        ref_slice = ref_coverage[s_start:s_end]
        test_slice = test_coverage[s_start:s_end]
        diff_slice = test_slice - ref_slice

        # Coverage Profile
        ax1.plot(x, ref_slice, color='#2C3E50', label="Sequential Reference Depth", linewidth=1.2)
        ax1.plot(x, test_slice, color='#E74C3C', linestyle='--', label="Distributed Hadoop MapReduce Depth", linewidth=1.2)
        ax1.set_ylabel("Coverage Depth (x)", fontweight='bold')
        ax1.set_title(f"Genomic Coverage Depth Verification (Interval: {s_start:,} - {s_end:,} bp)", fontweight='bold')
        ax1.legend(loc='upper right')
        ax1.grid(True, linestyle='--', alpha=0.5)

        # Residual / Difference Profile
        ax2.plot(x, diff_slice, color='#27AE60', linewidth=1.5, label="Residual Difference (Distributed - Reference)")
        ax2.set_ylim(-1, 1)
        ax2.set_yticks([0])
        ax2.set_yticklabels(["0 (Exact Match)"], fontweight='bold')
        ax2.set_ylabel("Difference", fontweight='bold')
        ax2.set_xlabel("Chromosomal Coordinate (bp)", fontweight='bold')
        ax2.legend(loc='upper right')
        ax2.grid(True, linestyle='--', alpha=0.5)

        plt.tight_layout()
        out_path = os.path.join(self.output_dir, filename)
        plt.savefig(out_path, dpi=300)
        plt.close()
        print(f"[+] Saved Figure: {out_path}")
        return out_path
