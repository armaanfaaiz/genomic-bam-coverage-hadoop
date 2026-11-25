# Local Multi-Node Apache Hadoop Cluster (Docker)
## Final Year Project: Distributed Exact BAM Coverage on Heterogeneous Hadoop

This setup runs a **genuine, multi-node Apache Hadoop 3.2.1 cluster** on your local machine using Docker containers, providing the full Hadoop ecosystem (HDFS, YARN, and Web UIs) with **zero cloud costs** and **no credit card required**.

---

## 1. Cluster Architecture

The Docker Compose configuration simulates a **heterogeneous 4-worker cluster**:

```text
                               ┌─────────────────────────────────┐
                               │  hadoop-namenode (Port 9870)    │
                               │  hadoop-resourcemanager (:8088) │
                               └────────────────┬────────────────┘
                                                │
         ┌──────────────────┬───────────────────┼──────────────────┐
         │                  │                   │                  │
┌────────▼────────┐┌────────▼────────┐┌─────────▼────────┐┌────────▼────────┐
│ hadoop-worker-1 ││ hadoop-worker-2 ││  hadoop-worker-3 ││ hadoop-worker-4 │
│ (2.0 CPU, 4GB)  ││ (1.5 CPU, 3GB)  ││  (1.0 CPU, 2GB)  ││ (0.5 CPU, 1GB)  │
│ 1.8x High Perf  ││ 1.2x Standard   ││  1.0x Baseline   ││ 0.6x Straggler  │
└─────────────────┘└─────────────────┘└──────────────────┘└─────────────────┘
```

---

## 2. Quick Start Guide

### Step 1: Ensure Docker Desktop Is Running
1. Open the **Windows Start Menu**.
2. Search for **Docker Desktop** and click it to open.
3. Wait ~30 seconds until the whale icon in your taskbar shows Docker is running.

### Step 2: Start the Hadoop Cluster
Open PowerShell and run:
```powershell
cd D:\Genomic_BAM_Coverage_Hadoop\docker_hadoop
.\start_cluster.ps1
```

Once started, open these URLs in your web browser:
- **YARN ResourceManager Web UI**: [http://localhost:8088](http://localhost:8088) (Shows active nodes and live job progress)
- **HDFS NameNode Web UI**: [http://localhost:9870](http://localhost:9870) (Shows storage capacity and file browser)

### Step 3: Run the Exact BAM Coverage Job
Submit the MapReduce job to YARN:
```powershell
.\run_hadoop_job.ps1
```
This automatically:
1. Copies the alignment dataset into HDFS (`/genomics_input/`).
2. Dispatches `mapper.py` and `reducer.py` via Hadoop Streaming.
3. Aggregates results across the 4 worker nodes.
4. Downloads the final exact BedGraph to `results\docker_output\`.

### Step 4: Stop the Cluster When Done
```powershell
.\stop_cluster.ps1
```

---

## 3. Why This Is Ideal for Your FYP Defense
- **Real Hadoop Environment**: You are not just running a simulation script; you are running authentic Apache Hadoop daemons (HDFS NameNode, DataNodes, YARN NodeManagers).
- **Offline & Reliable**: No internet connection needed, no cloud credits expiring, no payment gateway issues during your project presentation.
- **Physical Heterogeneity**: Because each worker container has strict CPU and memory limits (`cpus: 2.0`, `cpus: 0.5`), slow Worker 4 truly experiences computational delays, mathematically proving your straggler mitigation hypothesis in a live demo.
