<#
.SYNOPSIS
  Starts InvestAd locally (FastAPI on :8000, Vite on :5173) as detached processes and opens the app.
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\start.ps1            # start now
  powershell -ExecutionPolicy Bypass -File scripts\start.ps1 -AtLogon   # also start on every Windows logon
  powershell -ExecutionPolicy Bypass -File scripts\start.ps1 -RemoveAtLogon
#>
param([switch]$AtLogon, [switch]$RemoveAtLogon, [switch]$NoBrowser)

$root = Split-Path -Parent $PSScriptRoot
$logs = Join-Path $root ".logs"
$taskName = "InvestAd"
New-Item -ItemType Directory -Force $logs | Out-Null

if ($RemoveAtLogon) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Removed the logon task."; return
}
if ($AtLogon) {
    $action = New-ScheduledTaskAction -Execute "powershell.exe" `
        -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$PSCommandPath`" -NoBrowser"
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger (New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME) `
        -Settings (New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries) -Force | Out-Null
    Write-Host "InvestAd will now start automatically when you log on."
}

function Test-Port($port) { [bool](Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) }

$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "No virtualenv at $python - run: python -m venv .venv; .venv\Scripts\pip install -r requirements-dev.txt" }

if (Test-Port 8000) { Write-Host "Backend already running on :8000" } else {
    Start-Process -FilePath $python -WorkingDirectory $root -WindowStyle Hidden `
        -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000" `
        -RedirectStandardOutput "$logs\backend.out.log" -RedirectStandardError "$logs\backend.log"
    Write-Host "Backend starting (logs: .logs\backend.log)"
}

$frontend = Join-Path $root "frontend"
if (-not (Test-Path "$frontend\node_modules")) { Push-Location $frontend; npm install; Pop-Location }
if (Test-Port 5173) { Write-Host "Frontend already running on :5173" } else {
    Start-Process -FilePath "cmd.exe" -WorkingDirectory $frontend -WindowStyle Hidden `
        -ArgumentList "/c", "npx vite --host 127.0.0.1 --port 5173 --strictPort > `"$logs\frontend.log`" 2>&1"
    Write-Host "Frontend starting (logs: .logs\frontend.log)"
}

$deadline = (Get-Date).AddSeconds(90)
while ((Get-Date) -lt $deadline) {
    try {
        Invoke-WebRequest "http://127.0.0.1:5173/api/health" -UseBasicParsing -TimeoutSec 3 | Out-Null
        Write-Host "InvestAd is up: http://localhost:5173"
        if (-not $NoBrowser) { Start-Process "http://localhost:5173" }
        return
    } catch { Start-Sleep -Seconds 2 }
}
Write-Warning "Not ready after 90s - check .logs\backend.log and .logs\frontend.log"
