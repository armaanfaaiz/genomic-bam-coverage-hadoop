# ==============================================================================
# Submit Exact BAM Coverage MapReduce Job to Local Docker Hadoop Cluster
# ==============================================================================

param (
    [string]$InputSamPath = "/workspace/data/synthetic_alignments.sam",
    [string]$OutputDir = "/output_coverage_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
)

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "  SUBMITTING EXACT BAM COVERAGE JOB TO HADOOP (YARN)" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan

# 1. Upload SAM data to HDFS if not already present
Write-Host "[*] Uploading input alignment data into HDFS..." -ForegroundColor Yellow
docker exec -i hadoop-namenode hdfs dfs -mkdir -p /genomics_input
docker exec -i hadoop-namenode hdfs dfs -put -f $InputSamPath /genomics_input/input_alignments.sam

# 2. Run Hadoop Streaming MapReduce Job
Write-Host "[*] Submitting Hadoop Streaming MapReduce Job..." -ForegroundColor Green
docker exec -i hadoop-resourcemanager yarn jar /opt/hadoop-3.2.1/share/hadoop/tools/lib/hadoop-streaming-3.2.1.jar `
    -files "/workspace/src/step4_mapreduce_coverage/hadoop_streaming/mapper.py,/workspace/src/step4_mapreduce_coverage/hadoop_streaming/reducer.py" `
    -mapper "python3 mapper.py" `
    -reducer "python3 reducer.py" `
    -input "/genomics_input/input_alignments.sam" `
    -output $OutputDir

# 3. Retrieve Output BedGraph from HDFS
Write-Host "`n[*] Extracting BedGraph results from HDFS..." -ForegroundColor Yellow
$localOutDir = "D:\Genomic_BAM_Coverage_Hadoop\results\docker_output"
New-Item -ItemType Directory -Force -Path $localOutDir | Out-Null
docker exec -i hadoop-namenode hdfs dfs -get "$OutputDir/*" "/workspace/results/docker_output/"

Write-Host "`n======================================================================" -ForegroundColor Green
Write-Host " JOB COMPLETED SUCCESSFULLY ON DOCKER HADOOP CLUSTER!" -ForegroundColor Green
Write-Host " Results downloaded to: $localOutDir" -ForegroundColor Green
Write-Host " View YARN execution metrics at: http://localhost:8088" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Green
