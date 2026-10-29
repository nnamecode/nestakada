param([int]$Port = 8765)

throw 'Автоматический watchdog отключён после двух неудачных запусков. См. PREVIEW-01 в docs/tasks.md.'

$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$previewUrl = "http://127.0.0.1:$Port/work/public-light-v4.html"
$previewWorkDir = Join-Path $projectRoot 'work'
$watchdogPidPath = Join-Path $previewWorkDir '.public-preview-watchdog.pid'
$watchdogScript = Join-Path $PSScriptRoot 'public-preview-watchdog.ps1'
$bundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'

function Test-PreviewHealth {
    try {
        $response = Invoke-WebRequest -Uri $previewUrl -UseBasicParsing -TimeoutSec 3
        return $response.StatusCode -eq 200
    }
    catch {
        return $false
    }
}

$previewInitiallyHealthy = Test-PreviewHealth
$watchdogIsRunning = $false

if (Test-Path -LiteralPath $watchdogPidPath) {
    $existingWatchdogPid = Get-Content -LiteralPath $watchdogPidPath -ErrorAction SilentlyContinue
    if ($existingWatchdogPid -and (Get-Process -Id $existingWatchdogPid -ErrorAction SilentlyContinue)) {
        $watchdogIsRunning = $true
        Write-Output "Watchdog PID $existingWatchdogPid is already running; waiting for preview."
    }
    else {
        Remove-Item -LiteralPath $watchdogPidPath -Force -ErrorAction SilentlyContinue
    }
}

if ($previewInitiallyHealthy -and $watchdogIsRunning) {
    Write-Output "Preview is already available and monitored: $previewUrl"
    exit 0
}

if (-not $watchdogIsRunning) {
    if (-not (Test-Path -LiteralPath $bundledPython)) {
        throw "Bundled Python was not found: $bundledPython"
    }

    New-Item -ItemType Directory -Path $previewWorkDir -Force | Out-Null
    $watchdogProcess = Start-Process -FilePath 'powershell.exe' -ArgumentList @(
        '-NoProfile',
        '-ExecutionPolicy', 'Bypass',
        '-File', $watchdogScript,
        '-Port', "$Port"
    ) -WindowStyle Hidden -PassThru
    Write-Output "Started preview watchdog PID $($watchdogProcess.Id)."
}

for ($attempt = 0; $attempt -lt 20; $attempt++) {
    Start-Sleep -Milliseconds 500
    if (Test-PreviewHealth) {
        Write-Output "Preview is available: $previewUrl"
        exit 0
    }
}

throw "Preview did not become available. Check work\public-preview-watchdog.log."
