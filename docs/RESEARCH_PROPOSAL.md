# Final Year Project Research Proposal

## Title
**Sampling-Guided Machine Learning-Based Adaptive Partitioning and Heterogeneity-Aware Scheduling for Exact BAM Coverage Computation on Hadoop**

---

## 1. Abstract
Next-Generation Sequencing (NGS) produces massive quantities of genomic alignment data stored in BAM/SAM formats. Calculating exact per-base depth of coverage is a cornerstone of variant calling, copy number variation (CNV) detection, and clinical genomic quality assurance. While Apache Hadoop MapReduce is widely used for distributed processing of massive genomic datasets, standard approaches suffer from severe **computational skew** and **straggler tasks**. Traditional static partitioning divides chromosomes into uniform genomic coordinates (e.g., fixed-width windows), ignoring significant variations in read depth, alignment complexity (CIGAR operations, indels, and soft clips), and mapping quality across genomic regions. Furthermore, standard Hadoop schedulers (such as FIFO or Fair Scheduler) treat cluster nodes as homogeneous, causing slow or resource-constrained nodes to be assigned computationally heavy partitions, exacerbating straggler latency.

To address these limitations, this project proposes an end-to-end framework integrating:
1. **Sampling-Guided Workload Prediction**: Extracting genomic complexity features from lightweight sampled regions and employing Random Forest and Gradient Boosting regression to estimate processing times (inspired by the LPA framework).
2. **Adaptive Genomic Partitioning**: Dynamically subdividing computationally skewed genomic hotspots into balanced sub-intervals bounded by minimum and maximum interval sizes.
3. **Heterogeneity-Aware Scheduling**: Profiling worker node capabilities via historical execution logs and Normalized Duration Time (NDT, inspired by ANODE), followed by a capacity-aware Heterogeneous Longest Processing Time (HLPT) scheduling strategy.
4. **Exact Distributed Coverage Computation**: Utilizing an optimal difference-array line sweep algorithm (inspired by PanDepth) within MapReduce to compute 100% exact per-base coverage.

Evaluation against traditional static partitioning demonstrates substantial reductions in total job makespan, straggler latency, and load variance while maintaining 100% exact coverage correctness.

---

## 2. Problem Statement & Motivation
### 2.1 The Computational Skew Problem in Genomic Big Data
In high-throughput sequencing pipelines:
- Coverage depth varies dramatically across the genome due to GC-content bias, repetitive DNA elements, targeted exome capture kinetics, and copy-number alterations.
- High-depth hotspots may harbor $5\times$ to $50\times$ the baseline coverage depth.
- Reads in complex regions feature dense insertions, deletions (indels), and soft-clipping, requiring significantly more compute cycles during alignment parsing and coverage aggregation.

When a chromosome is divided using **static equal-sized coordinate bins** (e.g., fixed 100 kbp windows):
$$\text{Partition}_k = [k \cdot W, (k+1) \cdot W)$$
The computational load $L_k$ per partition varies widely:
$$\text{Var}(L) \gg 0$$
Partitions spanning dense hotspots become computational bottlenecks, resulting in **straggler tasks** that hold back the completion of the entire MapReduce job.

### 2.2 Worker Node Heterogeneity
In real-world data centers and academic research clusters:
- Compute nodes feature diverse hardware generations (varying CPU clock speeds, core counts, RAM bandwidth, and I/O throughput).
- Existing Hadoop schedulers (FIFO / Fair) assign tasks without factoring in node-specific processing rates.
- If a computationally heavy genomic block is dispatched to a slow or degraded worker node, straggler delay increases multiplicatively.

---

## 3. Related Work & Research Foundation
This research bridges and advances foundational concepts from recent literature:

1. **LPA: Learning-based Parallel Acceleration for HaplotypeCaller** (Lai et al., *BMC Bioinformatics*, 2025):
   - Demonstrates that machine learning (CatBoost/Random Forest) can accurately predict genomic execution times from feature sets.
   - Proposes splitting expensive blocks to reduce parallel execution skew.
   - *Our Adaptation*: We extend this paradigm to distributed BAM coverage computation, tailoring feature engineering to alignment depths, CIGAR operations, and difference-array characteristics.

2. **ANODE: Adaptive Node-Oriented Data Placement for Heterogeneous Hadoop Clusters** (Verma, Kumar & Naik, *IEEE Access*, 2025):
   - Utilizes historical Hadoop execution logs to estimate the relative performance of heterogeneous worker nodes using Normalized Duration Time (NDT).
   - *Our Adaptation*: While ANODE focuses on data placement, we adapt the worker-profiling concept into a dynamic **Heterogeneous Longest Processing Time (HLPT)** task allocation scheduler.

3. **Distributed NGS Data Processing under Map-Reduce** (Samaddar, Sinha & De, 2019):
   - Establishes foundational MapReduce pipelines for genomic alignments.
   - Highlights the necessity of efficient mapping and interval reduction.

4. **PanDepth: Ultrafast and Efficient Genomic Coverage Calculation** (Yu & Shi, 2024):
   - Proves that difference array / prefix sum line sweep algorithms compute exact coverage in $O(N_{\text{reads}} + L_{\text{interval}})$ time, outperforming traditional naive counters.
   - *Our Adaptation*: We embed this optimal difference-array engine into the Map phase of Hadoop MapReduce.

---

## 4. Proposed Methodology & Mathematical Formulation

### Stage 1: Fast Sampling & Workload Prediction
To avoid the overhead of a full preliminary pass, a uniform reservoir sample (sampling fraction $\alpha \approx 5\%$) is drawn across each interval:
$$\text{Sample}(R_k) \subset R_k, \quad |\text{Sample}(R_k)| = \alpha \cdot |R_k|$$

From the sample, we extract an 8-dimensional feature vector $\mathbf{x}_k$:
1. **Sampled Read Count** ($\hat{N}_k$): Estimated total alignments.
2. **Read Density** ($\rho_k = \hat{N}_k / \Delta L_k$): Alignments per base pair.
3. **Estimated Mean Depth** ($\bar{D}_k = (\hat{N}_k \cdot \bar{L}_{\text{read}}) / \Delta L_k$).
4. **CIGAR Mismatch & Clip Rate** ($c_k$): Frequency of `I`, `D`, `S` operations.
5. **Indel Frequency** ($f_{\text{indel}}$): Proportion of alignments harboring insertions/deletions.
6. **Mean Mapping Quality** ($\overline{\text{MAPQ}}_k$): Confidence of read alignments.
7. **GC Content Bias** ($g_k$): Proportion of G/C bases affecting polymerase kinetics.
8. **Interval Span** ($\Delta L_k = \text{end}_k - \text{start}_k$).

A Random Forest Regressor $f_{\boldsymbol{\theta}}(\mathbf{x}_k)$ is trained to predict baseline execution time $\hat{T}_k$:
$$\hat{T}_k = f_{\boldsymbol{\theta}}(\mathbf{x}_k)$$
Trained by minimizing the Mean Squared Error:
$$\mathcal{L}(\boldsymbol{\theta}) = \frac{1}{M}\sum_{k=1}^M \left( T_k^{\text{actual}} - f_{\boldsymbol{\theta}}(\mathbf{x}_k) \right)^2$$

### Stage 2: Adaptive Genomic Partitioning
Let $\hat{T}_{\text{median}}$ and $Q_{75}(\hat{T})$ denote the median and 75th percentile predicted execution times across all candidate intervals.
For any region $k$ where:
$$\hat{T}_k > Q_{75}(\hat{T}) \quad \text{and} \quad \Delta L_k \ge 2 \cdot L_{\min}$$
The region is adaptively subdivided into $s_k$ sub-partitions:
$$s_k = \min \left( \left\lceil \frac{\hat{T}_k}{\hat{T}_{\text{median}}} \right\rceil, \; \left\lfloor \frac{\Delta L_k}{L_{\min}} \right\rfloor, \; s_{\max} \right)$$
Each sub-partition inherits an expected workload $\hat{T}_{k, j} \approx \hat{T}_k / s_k$, significantly shrinking peak task load and variance.

### Stage 3: Heterogeneity-Aware Worker Profiling & HLPT Scheduling
Following ANODE, we define the processing rate $R_i$ of worker node $i$ over $N_i$ historically completed tasks:
$$R_i = \frac{1}{N_i} \sum_{j=1}^{N_i} \frac{W_j}{T_{i, j}}$$
The cluster average rate and relative capacity factor $C_i$ are:
$$R_{\text{avg}} = \frac{1}{M} \sum_{i=1}^M R_i, \qquad C_i = \frac{R_i}{R_{\text{avg}}}$$
The Normalized Duration Time (NDT) is:
$$\text{NDT}_i = \frac{1}{C_i} = \frac{R_{\text{avg}}}{R_i}$$

#### HLPT (Heterogeneous Longest Processing Time) Scheduling Algorithm:
1. Sort all genomic partition tasks in descending order of predicted baseline workload:
   $$\hat{T}_{(1)} \ge \hat{T}_{(2)} \ge \dots \ge \hat{T}_{(P)}$$
2. Initialize current cumulative completion time for each worker: $\Lambda_i = 0, \forall i \in \{1, \dots, M\}$.
3. For each partition task $j = 1$ to $P$:
   Assign task $j$ to worker node $i^*$ that achieves the minimum completion time:
   $$i^* = \arg\min_{i \in \{1, \dots, M\}} \left( \Lambda_i + \frac{\hat{T}_{(j)}}{C_i} \right)$$
   Update worker timeline:
   $$\Lambda_{i^*} \leftarrow \Lambda_{i^*} + \frac{\hat{T}_{(j)}}{C_{i^*}}$$

### Stage 4: Exact Distributed Coverage Computation
Within the Map phase, each assigned partition $[S, E)$ is computed using difference-array prefix summation:
$$\Delta[p - S] \leftarrow \Delta[p - S] + 1, \qquad \Delta[q - S] \leftarrow \Delta[q - S] - 1$$
Exact depth at chromosomal coordinate $x \in [S, E)$ is recovered by prefix scan:
$$D(x) = \sum_{k=0}^{x - S} \Delta[k]$$
Contiguous runs of identical depth are emitted as BedGraph segments:
$$\text{chrom} \quad \text{start} \quad \text{end} \quad D(x)$$
The Reduce phase aggregates boundary records and verifies contiguous stitching across partition borders.

---

## 5. Performance Evaluation Framework
We evaluate four experimental configurations on a heterogeneous cluster:
1. **Baseline**: Static Partitioning + FIFO Scheduling (Standard Hadoop YARN baseline)
2. **Intermediate 1**: Static Partitioning + HLPT Scheduling
3. **Intermediate 2**: ML Adaptive Partitioning + FIFO Scheduling
4. **Proposed Framework**: ML Adaptive Partitioning + HLPT Scheduling

### Key Metrics:
- **Makespan ($T_{\text{make}}$)**: Total wall-clock time from job initiation to final output aggregation.
- **Speedup ($S$)**: $T_{\text{make}}^{\text{baseline}} / T_{\text{make}}^{\text{proposed}}$.
- **Straggler Latency**: $\max_i(\Lambda_i) - \min_i(\Lambda_i)$.
- **Cluster Resource Utilization**: Ratio of total active compute time to $(M \cdot T_{\text{make}})$.
- **ML Prediction Error**: Mean Absolute Error (MAE), Root Mean Squared Error (RMSE), and $R^2$.
- **Coverage Concordance**: Percentage of genomic bases with exact depth equivalence against sequential Samtools/Mosdepth references ($100.0\%$).

---

## 6. Project Timeline & Deliverables
- **Month 1-2**: Literature review, dataset preparation, feature extraction, and ML regression tuning.
- **Month 3-4**: Adaptive partitioning algorithm implementation, worker profiler, and HLPT scheduler design.
- **Month 5-6**: Hadoop MapReduce integration (Java & Streaming), difference-array coverage engine optimization.
- **Month 7-8**: Cluster benchmarking, comparative experiments, straggler analysis, thesis write-up, and defense.
