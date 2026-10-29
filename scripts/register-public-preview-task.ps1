param(
    [string]$TaskName = 'Estakada Public Preview',
    [int]$Port = 8765
)

$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$hiddenLauncher = Join-Path $PSScriptRoot 'start-public-preview-hidden.vbs'
$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name

if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "Bundled Python was not found: $pythonPath"
}

if (-not (Test-Path -LiteralPath $hiddenLauncher)) {
    throw "Hidden preview launcher was not found: $hiddenLauncher"
}

$wscriptPath = Join-Path $env:SystemRoot 'System32\wscript.exe'
$launcherArguments = "`"$hiddenLauncher`" $Port"
$action = New-ScheduledTaskAction -Execute $wscriptPath -Argument $launcherArguments -WorkingDirectory $projectRoot
$logonTrigger = New-ScheduledTaskTrigger -AtLogOn -User $currentUser
$healthTrigger = New-ScheduledTaskTrigger `
    -Once `
    -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes 1) `
    -RepetitionDuration (New-TimeSpan -Days 3650)
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId $currentUser -LogonType Interactive -RunLevel Limited

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger @($logonTrigger, $healthTrigger) `
    -Settings $settings `
    -Principal $principal `
    -Description 'Скрытый локальный сервер предпросмотра проекта Эстакада на 127.0.0.1:8765; контрольный запуск раз в минуту без дублирования процесса.' `
    -Force | Out-Null

Write-Output "Registered scheduled task: $TaskName"
