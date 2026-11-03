# Stops whatever is listening on the InvestAd ports (8000 backend, 5173 frontend).
foreach ($port in 8000, 5173) {
    $owners = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
    if (-not $owners) { Write-Host ":$port not running"; continue }
    foreach ($id in $owners) { Stop-Process -Id $id -Force -ErrorAction SilentlyContinue }
    Write-Host "Stopped :$port"
}
