# Genomic BAM Coverage on Heterogeneous Hadoop

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-brightgreen.svg)](https://www.python.org/)
[![Hadoop 3.3+](https://img.shields.io/badge/Hadoop-3.3+-orange.svg)](https://hadoop.apache.org/)

**Sampling-Guided Machine Learning-Based Adaptive Partitioning and Heterogeneity-Aware Scheduling for Exact BAM Coverage Computation on Hadoop**

Final Year Project (FYP) codebase and research framework for addressing **computational skew** and **straggler tasks** in distributed genomic data processing.

---

## 🌟 Key Research Novelty & Architecture

1. **Sampling-Guided Workload Prediction (Inspired by LPA - Lai et al., 2025)**:
   - Uses an ultrafast 5% sampling pass to extract genomic complexity features: read count, read density, estimated depth, CIGAR operation complexity (indels and soft clipping), mapping quality, and GC bias.
   - Evaluates and trains **Random Forest Regressors** and **Gradient Boosting Regressors** to accurately predict per-region computational runtimes.

2. **Adaptive Genomic Partitioning**:
   - Replaces traditional naive fixed-coordinate intervals (e.g., fixed 100 kbp windows) with workload-aware partitions.
   - Computes split factors $s_k$ for computational hotspots while preserving minimum ($L_{\min}$) and maximum ($L_{\max}$) interval constraints to prevent task fragmentation.

3. **Heterogeneity-Aware Worker Profiling & HLPT Scheduling (Inspired by ANODE - Verma et al., 2025)**:
   - Evaluates historical execution logs to compute each node's Normalized Duration Time (NDT) and relative Capacity Factor ($C_i$).
   - Proposes **Heterogeneous Longest Processing Time (HLPT)** scheduling that sorts tasks descending by workload and dispatches them to minimize $\min_i (\text{Load}_i + W_j / C_i)$.

4. **Exact Distributed BAM Coverage Computation (Inspired by PanDepth - Yu & Shi, 2024 & Samaddar et al., 2019)**:
   - Difference-array line sweep algorithm running in $O(N_{\text{reads}} + L_{\text{region}})$ time.
   - 100% exact per-base depth equivalence verified against standard sequential reference baselines.

5. **Comprehensive Comparative Benchmarking**:
   - Compares:
     - **Baseline**: Static Partitioning + FIFO Scheduling
     - **Scenario 2**: Static Partitioning + HLPT Scheduling
     - **Scenario 3**: ML Adaptive Partitioning + FIFO Scheduling
     - **Proposed Framework**: ML Adaptive Partitioning + HLPT Scheduling
   - Automatically generates publication-ready figures for project reports and defense presentations.

---

## 📁 Repository Directory Structure

```text
Genomic_BAM_Coverage_Hadoop/
├── config/
│   └── default_config.yaml              # Cluster nodes, genomic intervals, and algorithm params
├── data/
│   ├── generate_synthetic_data.py      # Generates realistic skewed BAM/SAM & BED intervals
│   ├── synthetic_alignments.sam        # Alignment dataset with hotspots
│   └── test_regions.bed                 # Genomic candidate intervals
├── src/
│   ├── step1_workload_prediction/
│   │   ├── feature_extractor.py        # Fast reservoir/stride feature extraction
│   │   ├── predictor_model.py          # Random Forest & Gradient Boosting regression models
│   │   └── train_workload_model.py     # Training and cross-validation pipeline
│   ├── step2_adaptive_partitioning/
│   │   ├── static_partitioner.py       # Traditional fixed-coordinate partitioner
│   │   └── adaptive_partitioner.py     # Workload-guided hotspot splitting
│   ├── step3_heterogeneity_scheduling/
│   │   ├── worker_profiler.py          # ANODE-style NDT and capacity factor estimation
│   │   └── hlpt_scheduler.py           # HLPT, LPT, FIFO, and Round-Robin schedulers
│   ├── step4_mapreduce_coverage/
│   │   ├── exact_coverage_engine.py    # PanDepth-style difference array exact coverage
│   │   ├── distributed_simulator.py    # Multi-worker heterogeneous cluster simulator
│   │   └── hadoop_streaming/
│   │       ├── mapper.py               # Hadoop Streaming Mapper
│   │       └── reducer.py              # Hadoop Streaming Reducer
│   └── step5_evaluation/
│       ├── metrics_calculator.py       # Makespan, straggler, speedup, and utilization metrics
│       ├── visualizer.py               # Publication-ready matplotlib figure generator
│       └── benchmark_runner.py         # 4-way comparative evaluation suite
├── hadoop_native/
│   ├── BamCoverageMapper.java          # Java MapReduce Mapper
│   ├── BamCoverageReducer.java         # Java MapReduce Reducer
│   ├── BamCoverageJob.java             # Java Driver class
│   └── pom.xml                         # Maven build configuration
├── results/                            # Generated plots, CSV logs, and model artifacts
├── docs/
│   ├── RESEARCH_PROPOSAL.md            # Complete academic FYP research proposal
│   └── METHODOLOGY_DIAGRAMS.md         # Architecture diagrams & flowcharts
├── run_pipeline.py                     # Master execution script
├── requirements.txt                    # Python dependencies
└── README.md                           # Project guide
```

---

## 🚀 Quick Start Guide

### 1. Installation
Clone the repository and install the dependencies:
```bash
pip install -r requirements.txt
```

### 2. Run the Full End-to-End Research Pipeline
Execute the master runner to generate synthetic data, train the ML model, partition genomic regions, schedule across heterogeneous workers, calculate exact coverage, and produce all evaluation plots:
```bash
python run_pipeline.py
```

### 3. Generated Figures & Outputs (in `results/`)
- `fig1_makespan_speedup.png`: Wall-clock completion times and speedup factors.
- `fig2_straggler_mitigation.png`: Task duration distributions and straggler elimination boxplots.
- `fig3_worker_timeline_gantt.png`: Heterogeneous worker execution timelines and idle-gap reduction.
- `fig4_ml_prediction_accuracy.png`: Regression parity plot ($R^2$, MAE, RMSE) and feature importance ranking.
- `fig5_coverage_correctness.png`: Base-level depth profile verifying 100% exact match against reference.
- `benchmark_comparison.csv`: Formatted table of makespan, speedup, and cluster utilization metrics.

---

## 🛠️ Deploying on Native Hadoop Clusters

### Option A: Hadoop Streaming
```bash
hadoop jar $HADOOP_HOME/share/hadoop/tools/lib/hadoop-streaming-*.jar \
  -files src/step4_mapreduce_coverage/hadoop_streaming/mapper.py,src/step4_mapreduce_coverage/hadoop_streaming/reducer.py \
  -mapper "python mapper.py" \
  -reducer "python reducer.py" \
  -input /hdfs/path/to/partitions_and_alignments \
  -output /hdfs/path/to/output_bedgraph
```

### Option B: Native Java MapReduce
```bash
cd hadoop_native
mvn clean package
hadoop jar target/bam-coverage-mr-1.0.0.jar org.genomics.hadoop.BamCoverageJob \
  /hdfs/path/to/alignments.sam \
  /hdfs/path/to/output_bedgraph
```

---

## 📚 Academic References
1. **LPA Framework**: Lai et al. (2025), *Learning-based Parallel Acceleration for HaplotypeCaller*, BMC Bioinformatics.
2. **ANODE Framework**: Verma, Kumar and Naik (2025), *Adaptive Node-Oriented Data Placement for Heterogeneous Hadoop Clusters*, IEEE Access.
3. **Distributed NGS MapReduce**: Samaddar, Sinha and De (2019), *A Model for Distributed Processing and Analyses of NGS Data under Map-Reduce Paradigm*.
4. **PanDepth**: Yu and Shi (2024), *PanDepth: An Ultrafast and Efficient Genomic Tool for Coverage Calculation*.
