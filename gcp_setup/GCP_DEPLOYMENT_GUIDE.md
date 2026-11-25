# Google Cloud Platform (GCP) Dataproc Deployment Guide
## Distributed Genomic BAM Coverage on Heterogeneous Hadoop

This guide walks you through deploying and executing your research project on a real, multi-node Google Cloud Dataproc Hadoop cluster with **15 GB+ BAM alignment files**.

---

## 1. Prerequisites: GCP Free Credits & SDK

### 1.1 Activate Free Cloud Credits ($300)
- Google Cloud provides **\$300 in free credits** for 90 days for new users, students, and researchers.
- Sign up at [https://cloud.google.com/free](https://cloud.google.com/free).
- Create a new project named e.g. `genomic-coverage-fyp`.

### 1.2 Install Google Cloud SDK (gcloud CLI) on Windows
1. Download the Google Cloud SDK installer:  
   👉 [https://dl.google.com/dl/cloudsdk/channels/rapid/GoogleCloudSDKInstaller.exe](https://dl.google.com/dl/cloudsdk/channels/rapid/GoogleCloudSDKInstaller.exe)
2. Run the installer and keep default options.
3. Open PowerShell and authenticate your Google account:
   ```powershell
   gcloud auth login
   gcloud config set project YOUR_PROJECT_ID
   ```

---

## 2. Generating or Downloading 15GB BAM Files

### Option A: High-Throughput Streaming Generation (Offline, No Download)
Generate a high-fidelity synthetic 15 GB SAM file with computational skew hotspots:
```powershell
cd D:\Genomic_BAM_Coverage_Hadoop
python data\stream_generate_15gb.py --size_gb 15.0 --output data\alignments_15gb.sam
```
*Memory footprint stays under 150 MB RAM throughout generation.*

### Option B: Real 1000 Genomes Project WGS BAM
Download an authentic human Chromosome 1 slice (~12–14 GB) from the 1000 Genomes Project:
```powershell
python data\download_real_15gb_bam.py --dataset 1000genomes_na12878_chr1
```

---

## 3. One-Click Automated Dataproc Execution

We have automated the entire Google Cloud workflow (enabling APIs, creating GCS buckets, uploading 15GB data, provisioning heterogeneous nodes, running Hadoop MapReduce, and downloading results).

In PowerShell, run:
```powershell
cd D:\Genomic_BAM_Coverage_Hadoop\gcp_setup
.\setup_gcp_dataproc.ps1 -ProjectId "YOUR_PROJECT_ID" -LocalSamPath "..\data\alignments_15gb.sam"
```

### What This Script Does Automatically:
1. **Enables GCP APIs**: `dataproc.googleapis.com`, `storage-component.googleapis.com`.
2. **Creates GCS Bucket**: `gs://genomics-hadoop-<project-id>/`.
3. **Uploads 15GB Alignments**: Uses multi-threaded parallel upload (`gsutil -m cp`).
4. **Provisions Heterogeneous Cluster**:
   - Master node: `e2-standard-4` (4 vCPU, 16 GB RAM)
   - Primary workers: 4x `n2-standard-4` (4 vCPU, 16 GB RAM each)
   - Secondary / spot workers: 2x `e2-standard-2` (2 vCPU, 8 GB RAM each)
5. **Submits MapReduce Job**: Streams your Python mapper and reducer through Hadoop YARN.
6. **Downloads Output BedGraph**: Saves final per-base coverage to `results/gcp_output/`.

---

## 4. Manual Deployment via Google Cloud Web Console

If you prefer using the browser GUI instead of the command line:

1. **Go to Google Cloud Console**: [https://console.cloud.google.com](https://console.cloud.google.com)
2. **Create a Cloud Storage Bucket**:
   - Search for **Cloud Storage** $\rightarrow$ Click **Create**.
   - Name: `genomics-data-bucket-unique` $\rightarrow$ Region: `us-central1`.
   - Upload `mapper.py`, `reducer.py`, and `alignments_15gb.sam`.
3. **Create Dataproc Cluster**:
   - Search for **Dataproc** $\rightarrow$ Click **Create Cluster** $\rightarrow$ Choose **Cluster on Compute Engine**.
   - Cluster Name: `genomics-hetero-cluster`.
   - Region: `us-central1`.
   - Master node: `e2-standard-4` (4 vCPU, 16 GB RAM).
   - Primary workers: 4 nodes, Machine type: `n2-standard-4`.
   - Secondary workers: 2 nodes, Preemptible / Spot `e2-standard-2`.
   - Click **Create**. (Takes ~90 seconds to initialize).
4. **Submit MapReduce Job**:
   - In the Dataproc menu, click **Jobs** $\rightarrow$ **Submit Job**.
   - Job type: **Hadoop**.
   - Main class or jar: `org.apache.hadoop.streaming.HadoopStreaming`.
   - Arguments:
     ```text
     -files gs://YOUR_BUCKET/scripts/mapper.py,gs://YOUR_BUCKET/scripts/reducer.py
     -mapper python3 mapper.py
     -reducer python3 reducer.py
     -input gs://YOUR_BUCKET/data/alignments_15gb.sam
     -output gs://YOUR_BUCKET/output_bedgraph
     ```
   - Click **Submit**.

---

## 5. Cost Breakdown & Budget Control

| Resource | Units | Machine Type | Hourly Cost | 15-Min Run Cost |
| :--- | :---: | :---: | :---: | :---: |
| Master Node | 1 | `e2-standard-4` | \$0.134 / hr | \$0.034 |
| Primary Workers | 4 | `n2-standard-4` | \$0.197 / hr each | \$0.197 |
| Secondary Spot Workers | 2 | `e2-standard-2` | \$0.020 / hr each | \$0.010 |
| Dataproc Management Fee | 24 vCPUs | - | \$0.010 / vCPU-hr | \$0.060 |
| Cloud Storage (15GB) | 15 GB | Standard | \$0.020 / GB-month | \$0.010 |
| **Total Estimated Run Cost** | | | | **~\$0.31 USD** |

> [!CAUTION]
> Always terminate your Dataproc cluster after your benchmark run to stop Compute Engine instance billing:
> ```powershell
> gcloud dataproc clusters delete genomics-hetero-cluster --region=us-central1 --quiet
> ```
