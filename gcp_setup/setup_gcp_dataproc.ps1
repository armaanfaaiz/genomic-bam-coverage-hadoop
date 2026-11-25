# ==============================================================================
# Google Cloud Dataproc Automation Script (PowerShell for Windows)
# Distributed Genomic BAM Coverage on Heterogeneous Hadoop
# ==============================================================================

param (
    [string]$ProjectId = "",
    [string]$Region = "us-central1",
    [string]$ClusterName = "genomics-hetero-cluster",
    [string]$BucketName = "",
    [string]$LocalSamPath = "data\alignments_15gb.sam"
)

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "  GOOGLE CLOUD PLATFORM (GCP) - DATAPROC HADOOP DEPLOYMENT" -ForegroundColor Cyan
Write-Host "  Genomic BAM Coverage on Heterogeneous Hadoop" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan

# 1. Check if gcloud is installed
if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) {
    Write-Host "[!] 'gcloud' CLI is not found on your system." -ForegroundColor Red
    Write-Host "[*] Please install the Google Cloud SDK from:" -ForegroundColor Yellow
    Write-Host "    https://cloud.google.com/sdk/docs/install#windows" -ForegroundColor Yellow
    Write-Host "[*] After installation, run: gcloud auth login" -ForegroundColor Yellow
    exit 1
}

# 2. Project ID handling
if ([string]::IsNullOrWhiteSpace($ProjectId)) {
    $currentProject = (gcloud config get-value project 2>$null)
    if (-not [string]::IsNullOrWhiteSpace($currentProject)) {
        $ProjectId = $currentProject
        Write-Host "[+] Using active GCP Project: $ProjectId" -ForegroundColor Green
    } else {
        $ProjectId = Read-Host "Enter your GCP Project ID"
        gcloud config set project $ProjectId
    }
}

if ([string]::IsNullOrWhiteSpace($BucketName)) {
    $BucketName = "genomics-hadoop-$ProjectId-$(Get-Random -Minimum 1000 -Maximum 9999)"
}

Write-Host "`n[*] Configuration Summary:" -ForegroundColor Yellow
Write-Host "  - GCP Project ID : $ProjectId"
Write-Host "  - Region         : $Region"
Write-Host "  - Cluster Name   : $ClusterName"
Write-Host "  - GCS Bucket     : gs://$BucketName"
Write-Host "  - Local Input    : $LocalSamPath"

# 3. Enable Required Google Cloud APIs
Write-Host "`n[*] Enabling Google Cloud APIs (Dataproc & Cloud Storage)..." -ForegroundColor Yellow
gcloud services enable dataproc.googleapis.com storage-component.googleapis.com compute.googleapis.com

# 4. Create GCS Bucket and Upload Data
Write-Host "`n[*] Checking Cloud Storage Bucket: gs://$BucketName..." -ForegroundColor Yellow
gsutil ls -b "gs://$BucketName" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[+] Creating GCS Bucket: gs://$BucketName in $Region..." -ForegroundColor Green
    gsutil mb -p $ProjectId -l $Region "gs://$BucketName"
}

# Upload MapReduce scripts
Write-Host "[*] Uploading Hadoop Streaming Mapper and Reducer..." -ForegroundColor Yellow
gsutil cp src\step4_mapreduce_coverage\hadoop_streaming\mapper.py "gs://$BucketName/scripts/mapper.py"
gsutil cp src\step4_mapreduce_coverage\hadoop_streaming\reducer.py "gs://$BucketName/scripts/reducer.py"

# Upload SAM dataset if exists
if (Test-Path $LocalSamPath) {
    Write-Host "[*] Uploading local alignment file ($LocalSamPath) to gs://$BucketName/data/..." -ForegroundColor Yellow
    gsutil -m cp $LocalSamPath "gs://$BucketName/data/input_alignments.sam"
} else {
    Write-Host "[!] Local file '$LocalSamPath' not found. Ensure synthetic or real BAM is generated first." -ForegroundColor Yellow
}

# 5. Create Heterogeneous Dataproc Cluster
Write-Host "`n[*] Provisioning Heterogeneous Hadoop Dataproc Cluster: $ClusterName..." -ForegroundColor Yellow
gcloud dataproc clusters create $ClusterName `
    --region=$Region `
    --zone="${Region}-a" `
    --image-version="2.1-debian11" `
    --master-machine-type="e2-standard-4" `
    --master-boot-disk-size="100GB" `
    --num-workers=4 `
    --worker-machine-type="n2-standard-4" `
    --worker-boot-disk-size="150GB" `
    --secondary-worker-type="spot" `
    --num-secondary-workers=2 `
    --secondary-worker-boot-disk-size="100GB" `
    --metadata="enable-oslogin=true"

# 6. Submit Hadoop Streaming MapReduce Job
Write-Host "`n[*] Submitting Distributed Exact Coverage Job to Dataproc..." -ForegroundColor Green
$outputDir = "gs://$BucketName/results/output_bedgraph_$(Get-Date -Format 'yyyyMMdd_HHmmss')"

gcloud dataproc jobs submit hadoop `
    --cluster=$ClusterName `
    --region=$Region `
    --class="org.apache.hadoop.streaming.HadoopStreaming" `
    --files="gs://$BucketName/scripts/mapper.py,gs://$BucketName/scripts/reducer.py" `
    -- `
    -mapper "python3 mapper.py" `
    -reducer "python3 reducer.py" `
    -input "gs://$BucketName/data/input_alignments.sam" `
    -output $outputDir

# 7. Download and Inspect Results
Write-Host "`n[*] Job finished! Downloading BedGraph results from $outputDir..." -ForegroundColor Green
New-Item -ItemType Directory -Force -Path "results\gcp_output" | Out-Null
gsutil -m cp -r "$outputDir/*" "results\gcp_output\"

Write-Host "`n======================================================================" -ForegroundColor Green
Write-Host " GCP DATAPROC EXECUTION COMPLETED SUCCESSFULLY!" -ForegroundColor Green
Write-Host " Output BedGraph saved locally in: results\gcp_output\" -ForegroundColor Green
Write-Host " NOTE: To avoid ongoing Google Cloud charges, delete the cluster when done:" -ForegroundColor Yellow
Write-Host "       gcloud dataproc clusters delete $ClusterName --region=$Region --quiet" -ForegroundColor Yellow
Write-Host "======================================================================" -ForegroundColor Green
