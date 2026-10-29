param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$PythonPath = (Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'),
    [int]$Port = 8765
)

throw 'Этот черновой watchdog отключён после двух неудачных запусков. См. PREVIEW-01 в docs/tasks.md.'

$ErrorActionPreference = 'Stop'

$previewWorkDir = Join-Path $ProjectRoot 'work'
$watchdogPidPath = Join-Path $previewWorkDir '.public-preview-watchdog.pid'
$serverPidPath = Join-Path $previewWorkDir '.public-preview-server.pid'
$watchdogLogPath = Join-Path $previewWorkDir 'public-preview-watchdog.log'
$previewUrl = "http://127.0.0.1:$Port/work/public-light-v4.html"
$consecutiveStartFailures = 0

if (-not (Test-Path -LiteralPath $PythonPath)) {
    throw "Bundled Python was not found: $PythonPath"
}

function Write-PreviewLog {
    param([string]$Message)
    $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Add-Content -LiteralPath $watchdogLogPath -Value "[$timestamp] $Message" -Encoding UTF8
}

function Test-PreviewHealth {
    try {
        $response = Invoke-WebRequest -Uri $previewUrl -UseBasicParsing -TimeoutSec 3
        return $response.StatusCode -eq 200
    }
    catch {
        return $false
    }
}

New-Item -ItemType Directory -Path $previewWorkDir -Force | Out-Null
Set-Content -LiteralPath $watchdogPidPath -Value $PID -Encoding ASCII
Write-PreviewLog "Watchdog started (PID $PID)."

try {
    while ($true) {
        if (-not (Test-PreviewHealth)) {
            $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
            $stdoutPath = Join-Path $previewWorkDir "public-preview-$stamp.out.log"
            $stderrPath = Join-Path $previewWorkDir "public-preview-$stamp.err.log"
            Write-PreviewLog 'Preview is unavailable; starting a new server process.'

            try {
                $serverProcess = Start-Process -FilePath $PythonPath `
                    -ArgumentList @('-m', 'http.server', "$Port", '--bind', '127.0.0.1', '--directory', $ProjectRoot) `
                    -WindowStyle Hidden -PassThru `
                    -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
                Set-Content -LiteralPath $serverPidPath -Value $serverProcess.Id -Encoding ASCII

                $healthy = $false
                for ($attempt = 0; $attempt -lt 20; $attempt++) {
                    Start-Sleep -Milliseconds 500
                    if (Test-PreviewHealth) {
                        $healthy = $true
                        break
                    }
                }

                if (-not $healthy) {
                    throw "Server process $($serverProcess.Id) did not become healthy."
                }

                $consecutiveStartFailures = 0
                Write-PreviewLog "Preview restored by server PID $($serverProcess.Id)."
            }
            catch {
                $consecutiveStartFailures++
                Write-PreviewLog "Start failure ${consecutiveStartFailures}: $($_.Exception.Message)"
                if ($consecutiveStartFailures -ge 2) {
                    throw 'Preview start failed twice; watchdog stopped to avoid a retry loop.'
                }
                Start-Sleep -Seconds 5
            }
        }

        Start-Sleep -Seconds 5
    }
}
finally {
    Write-PreviewLog 'Watchdog stopped.'
    Remove-Item -LiteralPath $watchdogPidPath -Force -ErrorAction SilentlyContinue
}
