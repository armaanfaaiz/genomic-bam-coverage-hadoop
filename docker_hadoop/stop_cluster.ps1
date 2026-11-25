# ==============================================================================
# Stop Docker Heterogeneous Apache Hadoop Cluster
# ==============================================================================

Write-Host "[*] Stopping Hadoop Containers..." -ForegroundColor Yellow
$composeDir = $PSScriptRoot
Set-Location $composeDir

if (Get-Command "docker-compose" -ErrorAction SilentlyContinue) {
    docker-compose down
} else {
    & "C:\Program Files\Docker\Docker\resources\bin\docker-compose.exe" down
}

Write-Host "[+] All Hadoop containers stopped." -ForegroundColor Green
