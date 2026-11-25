# System Architecture & Methodology Diagrams

## 1. End-to-End System Architecture

```mermaid
flowchart TD
    subgraph DataInput ["1. Genomic Data & Cluster Input"]
        BAM["Input BAM/SAM Alignment Files"]
        REG["Target Genomic Regions (BED)"]
        LOGS["Historical Hadoop Execution Logs"]
    end

    subgraph Step1 ["Stage 1: Workload Prediction (LPA Inspired)"]
        SAMP["Fast Sampling Module (5% Stride/Reservoir)"]
        FEAT["Genomic Feature Extractor<br/>(Read Count, Density, Depth, CIGAR, Indels, MAPQ, GC)"]
        ML_MODEL["Trained Workload Predictor<br/>(Random Forest / CatBoost Regression)"]
        PRED_TIME["Predicted Processing Times {T_k}"]
        
        BAM --> SAMP
        REG --> SAMP
        SAMP --> FEAT
        FEAT --> ML_MODEL
        ML_MODEL --> PRED_TIME
    end

    subgraph Step2 ["Stage 2: Adaptive Genomic Partitioning"]
        THRESHOLD{"Predicted Time T_k > Q75<br/>AND Span >= 2*MinSize?"}
        SPLIT["Adaptive Sub-Partitioning<br/>(Proportional Split s_k)"]
        KEEP["Preserve Standard Partition"]
        PART_SET["Balanced Partition Task Queue"]

        PRED_TIME --> THRESHOLD
        THRESHOLD -- Yes --> SPLIT
        THRESHOLD -- No --> KEEP
        SPLIT --> PART_SET
        KEEP --> PART_SET
    end

    subgraph Step3 ["Stage 3: Heterogeneity-Aware Scheduling"]
        ANODE["Worker Profiler (ANODE Inspired)<br/>Computes NDT_i and Capacity Factors C_i"]
        HLPT["HLPT Task Scheduler<br/>Sort Descending & Minimize (Load_i + T_k / C_i)"]
        SCHEDULE["Heterogeneous Task Assignment Matrix"]

        LOGS --> ANODE
        PART_SET --> HLPT
        ANODE --> HLPT
        HLPT --> SCHEDULE
    end

    subgraph Step4 ["Stage 4: Distributed Exact Coverage Computation"]
        MAPPERS["Hadoop Map Tasks (Workers 1..M)"]
        DIFF_ARRAY["PanDepth Difference Array Sweep<br/>O(N_reads + L_interval)"]
        REDUCER["Hadoop Reduce Phase (Sort & Merge Contiguous Depths)"]
        FINAL_BEDGRAPH["Exact Genomic Coverage (BedGraph)"]

        SCHEDULE --> MAPPERS
        MAPPERS --> DIFF_ARRAY
        DIFF_ARRAY --> REDUCER
        REDUCER --> FINAL_BEDGRAPH
    end

    subgraph Step5 ["Stage 5: Verification & Benchmarking"]
        VALIDATE{"Exact Correctness Check<br/>vs Mosdepth/Samtools"}
        METRICS["Performance Evaluation<br/>(Makespan, Stragglers, Speedup, Utilization)"]
        CHARTS["Publication Figures"]

        FINAL_BEDGRAPH --> VALIDATE
        VALIDATE --> METRICS
        METRICS --> CHARTS
    end
```

---

## 2. HLPT Task Scheduling Decision Flowchart

```mermaid
flowchart TD
    Start(["Start Scheduling Job"]) --> FetchTasks["Retrieve Adaptively Partitioned Tasks"]
    FetchTasks --> SortTasks["Sort Tasks by Predicted Baseline Workload (Descending)<br/>T_(1) >= T_(2) >= ... >= T_(P)"]
    SortTasks --> InitLoads["Initialize Current Worker Cumulative Time:<br/>Load_i = 0 for all Workers i in {1..M}"]
    InitLoads --> TaskLoop{"More Tasks in Queue?"}

    TaskLoop -- Yes --> PickTask["Select Next Heaviest Task j with Workload T_j"]
    PickTask --> EvalWorkers["For each Worker i in {1..M}:<br/>Calculate Candidate Finish Time = Load_i + (T_j / Capacity_i)"]
    EvalWorkers --> BestWorker["Select Worker i* with Minimum Candidate Finish Time"]
    BestWorker --> Assign["Assign Task j to Worker i*<br/>Update: Load_i* = Load_i* + (T_j / Capacity_i*)"]
    Assign --> TaskLoop

    TaskLoop -- No --> Dispatch["Dispatch Task Assignment Plan to Hadoop Workers"]
    Dispatch --> End(["End Scheduling"])
```

---

## 3. Difference Array Line Sweep for Exact BAM Coverage

```mermaid
flowchart LR
    Read1["Read 1: [100, 250)"] --> DiffArray["Difference Array Delta[]"]
    Read2["Read 2: [180, 320)"] --> DiffArray
    Read3["Read 3: [200, 400)"] --> DiffArray

    DiffArray -- "Prefix Sum (Cumsum)" --> ExactDepth["Exact Per-Base Depths D(x)"]
    ExactDepth -- "Run-Length Compress" --> BedGraph["BedGraph Output Format<br/>chr1  100  180  1<br/>chr1  180  200  2<br/>chr1  200  250  3<br/>chr1  250  320  2<br/>chr1  320  400  1"]
```
