#!/usr/bin/env bash
# ==============================================================================
# Google Cloud Dataproc Automation Script (Bash for Linux/macOS)
# Distributed Genomic BAM Coverage on Heterogeneous Hadoop
# ==============================================================================

set -euo pipefail

PROJECT_ID="${1:-$(gcloud config get-value project 2>/dev/null || echo '')}"
REGION="${2:-us-central1}"
CLUSTER_NAME="${3:-genomics-hetero-cluster}"
BUCKET_NAME="${4:-genomics-hadoop-${PROJECT_ID}-$RANDOM}"
LOCAL_SAM_PATH="${5:-data/alignments_15gb.sam}"

if [[ -z "$PROJECT_ID" ]]; then
    read -p "Enter your GCP Project ID: " PROJECT_ID
    gcloud config set project "$PROJECT_ID"
fi

echo "======================================================================"
echo "  GOOGLE CLOUD PLATFORM (GCP) - DATAPROC HADOOP DEPLOYMENT"
echo "  Project ID: $PROJECT_ID | Region: $REGION | Cluster: $CLUSTER_NAME"
echo "======================================================================"

# 1. Enable Services
echo "[*] Enabling Dataproc and Cloud Storage APIs..."
gcloud services enable dataproc.googleapis.com storage-component.googleapis.com compute.googleapis.com

# 2. Create Bucket
echo "[*] Checking GCS bucket gs://$BUCKET_NAME..."
if ! gsutil ls -b "gs://$BUCKET_NAME" >/dev/null 2>&1; then
    echo "[+] Creating GCS bucket: gs://$BUCKET_NAME..."
    gsutil mb -p "$PROJECT_ID" -l "$REGION" "gs://$BUCKET_NAME"
fi

# 3. Upload Code & Data
echo "[*] Uploading MapReduce scripts..."
gsutil cp src/step4_mapreduce_coverage/hadoop_streaming/mapper.py "gs://$BUCKET_NAME/scripts/mapper.py"
gsutil cp src/step4_mapreduce_coverage/hadoop_streaming/reducer.py "gs://$BUCKET_NAME/scripts/reducer.py"

if [[ -f "$LOCAL_SAM_PATH" ]]; then
    echo "[*] Uploading local alignment file ($LOCAL_SAM_PATH) to GCS..."
    gsutil -m cp "$LOCAL_SAM_PATH" "gs://$BUCKET_NAME/data/input_alignments.sam"
fi

# 4. Provision Dataproc Cluster
echo "[*] Provisioning Heterogeneous Dataproc Cluster..."
gcloud dataproc clusters create "$CLUSTER_NAME" \
    --region="$REGION" \
    --zone="${REGION}-a" \
    --image-version="2.1-debian11" \
    --master-machine-type="e2-standard-4" \
    --master-boot-disk-size="100GB" \
    --num-workers=4 \
    --worker-machine-type="n2-standard-4" \
    --worker-boot-disk-size="150GB" \
    --secondary-worker-type="spot" \
    --num-secondary-workers=2 \
    --secondary-worker-boot-disk-size="100GB"

# 5. Submit Hadoop Streaming Job
OUTPUT_DIR="gs://$BUCKET_NAME/results/output_bedgraph_$(date +%Y%m%d_%H%M%S)"
echo "[*] Submitting Hadoop MapReduce job..."
gcloud dataproc jobs submit hadoop \
    --cluster="$CLUSTER_NAME" \
    --region="$REGION" \
    --class="org.apache.hadoop.streaming.HadoopStreaming" \
    --files="gs://$BUCKET_NAME/scripts/mapper.py,gs://$BUCKET_NAME/scripts/reducer.py" \
    -- \
    -mapper "python3 mapper.py" \
    -reducer "python3 reducer.py" \
    -input "gs://$BUCKET_NAME/data/input_alignments.sam" \
    -output "$OUTPUT_DIR"

# 6. Retrieve Results
mkdir -p results/gcp_output
echo "[*] Downloading output BedGraph to results/gcp_output..."
gsutil -m cp -r "$OUTPUT_DIR/*" results/gcp_output/

echo "======================================================================"
echo " GCP EXECUTION COMPLETE!"
echo " Remember to delete cluster to avoid ongoing costs:"
echo " gcloud dataproc clusters delete $CLUSTER_NAME --region=$REGION --quiet"
echo "======================================================================"
