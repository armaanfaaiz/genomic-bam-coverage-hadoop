# ==============================================================================
# Start Docker Heterogeneous Apache Hadoop Cluster
# ==============================================================================

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "  STARTING MULTI-NODE HADOOP CLUSTER (DOCKER)" -ForegroundColor Cyan
Write-Host "  Heterogeneous Cluster: Master + 4 Workers (1.8x, 1.2x, 1.0x, 0.6x)" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan

# 1. Check if Docker Desktop is running
try {
    $null = docker ps 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[!] Docker Desktop is not running." -ForegroundColor Yellow
        Write-Host "[*] Please start Docker Desktop from your Windows Start Menu, wait until it starts, and re-run this script." -ForegroundColor Yellow
        exit 1
    }
} catch {
    Write-Host "[!] Docker command failed. Please ensure Docker Desktop is started." -ForegroundColor Red
    exit 1
}

# 2. Launch cluster via docker-compose
$composeDir = $PSScriptRoot
Set-Location $composeDir

Write-Host "[*] Launching Hadoop Containers..." -ForegroundColor Yellow
if (Get-Command "docker-compose" -ErrorAction SilentlyContinue) {
    docker-compose up -d
} else {
    & "C:\Program Files\Docker\Docker\resources\bin\docker-compose.exe" up -d
}

Write-Host "`n[*] Waiting 15 seconds for HDFS and YARN daemons to register..." -ForegroundColor Yellow
Start-Sleep -Seconds 15

# 3. Display live URLs and status
Write-Host "`n======================================================================" -ForegroundColor Green
Write-Host " HADOOP CLUSTER IS UP AND RUNNING!" -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Green
Write-Host " 🌐 YARN ResourceManager UI : http://localhost:8088" -ForegroundColor Cyan
Write-Host " 🌐 HDFS NameNode UI       : http://localhost:9870" -ForegroundColor Cyan
Write-Host " 🌐 Job History Server UI  : http://localhost:19888" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Green
Write-Host " To submit your exact BAM coverage MapReduce job, run:"
Write-Host " .\run_hadoop_job.ps1`n" -ForegroundColor Yellow
