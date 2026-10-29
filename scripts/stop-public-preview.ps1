param([int]$Port = 8765)

throw 'Черновые скрипты watchdog отключены. Прямой preview-сервер не останавливается этим файлом.'

$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$previewWorkDir = Join-Path $projectRoot 'work'
$watchdogPidPath = Join-Path $previewWorkDir '.public-preview-watchdog.pid'
$serverPidPath = Join-Path $previewWorkDir '.public-preview-server.pid'

foreach ($pidPath in @($watchdogPidPath, $serverPidPath)) {
    if (-not (Test-Path -LiteralPath $pidPath)) {
        continue
    }

    $previewProcessId = Get-Content -LiteralPath $pidPath -ErrorAction SilentlyContinue
    if ($previewProcessId) {
        Stop-Process -Id $previewProcessId -ErrorAction SilentlyContinue
    }
    Remove-Item -LiteralPath $pidPath -Force -ErrorAction SilentlyContinue
}

Write-Output "Preview processes recorded for port $Port have been stopped."
