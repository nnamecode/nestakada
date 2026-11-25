[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$scope = 'core18-runtime-20261125'
$runToken = [guid]::NewGuid().ToString('N')
$network = 'nestakada-core18-runtime-20261125-net'
$database = 'nestakada-core18-runtime-20261125-db'
$volume = "nestakada-core18-runtime-20261125-pgdata-$runToken"
$appImage = 'sha256:782f53c4a5e9473c5b93441adaac8da1ccbdcb93bc961a8d958c3b55c6e39986'
$postgresImage = 'sha256:de3d5ee43e308309e10730caead7dd880539d53f0275d977cd2f8c3f62b6eef7'
$source = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\src')).Path
$tools = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\tools')).Path
$generationTool = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\tools\rebuild7_generation.py')).Path
$foundationRequirements = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\environment\foundation\requirements.lock')).Path
$editorRequirements = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\environment\editor-package\requirements.lock')).Path

function Invoke-Docker {
    param([Parameter(Mandatory)][string[]]$Arguments)
    & docker @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "CORE18_DOCKER_COMMAND_FAILED"
    }
}

function Invoke-DockerOutput {
    param([Parameter(Mandatory)][string[]]$Arguments)
    $output = @(& docker @Arguments)
    if ($LASTEXITCODE -ne 0) {
        throw "CORE18_DOCKER_QUERY_FAILED"
    }
    return $output
}

function Assert-CleanScope {
    $containers = @(Invoke-DockerOutput -Arguments @('ps', '-aq', '--filter', "label=nestakada.scope=$scope"))
    $networks = @(Invoke-DockerOutput -Arguments @('network', 'ls', '-q', '--filter', "name=^$network`$"))
    $volumes = @(Invoke-DockerOutput -Arguments @('volume', 'ls', '-q', '--filter', "name=^$volume`$"))
    $labeledVolumes = @(
        Invoke-DockerOutput -Arguments @('volume', 'ls', '-q', '--filter', "label=nestakada.scope=$scope")
    )
    if (
        $containers.Count -ne 0 -or
        $networks.Count -ne 0 -or
        $volumes.Count -ne 0 -or
        $labeledVolumes.Count -ne 0
    ) {
        throw "CORE18_SCOPE_NOT_CLEAN"
    }
}

function Invoke-App {
    param([Parameter(Mandatory)][string[]]$Command)
    $arguments = @(
        'run', '--rm', '--name', ('nestakada-core18-runtime-' + [guid]::NewGuid().ToString('N')),
        '--label', "nestakada.scope=$scope", '--network', $network,
        '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
        '--user', '10001:10001', '--tmpfs', '/tmp:rw,nosuid,nodev,noexec,size=256m,uid=10001,gid=10001,mode=1777',
        '--mount', "type=bind,source=$source,target=/project/src,readonly",
        '--mount', "type=bind,source=$foundationRequirements,target=/project/environment/foundation/requirements.lock,readonly",
        '--mount', "type=bind,source=$editorRequirements,target=/project/environment/editor-package/requirements.lock,readonly",
        '--mount', "type=bind,source=$generationTool,target=/project/tools/rebuild7_generation.py,readonly",
        '--env', 'PYTHONDONTWRITEBYTECODE=1', '--env', 'DJANGO_SETTINGS_MODULE=config.settings.core18_runtime',
        '--env', 'ESTAKADA_CORE18_SYNTHETIC_RUNTIME=1', '--env', 'ESTAKADA_TEST_RUNTIME=1',
        '--env', 'ESTAKADA_TEST_DB_NAME=estakada_core18_test', '--env', 'ESTAKADA_TEST_DB_HOST=core18-db',
        '--env', 'ESTAKADA_TEST_DB_USER=postgres', '--env', 'ESTAKADA_DJANGO_SECRET=synthetic-core18-only',
        '--env', 'ESTAKADA_ALLOWED_HOSTS=testserver,localhost', '--env', 'ESTAKADA_DB_NAME=postgres',
        '--env', 'ESTAKADA_DB_USER=postgres', '--env', 'ESTAKADA_DB_PASSWORD=core18-synthetic-only',
        '--env', 'ESTAKADA_DB_HOST=core18-db', '--env', 'ESTAKADA_DB_PORT=5432',
        '--env', 'ESTAKADA_DB_SSLROOTCERT=/tmp/unused-ca', '--env', 'ESTAKADA_SERVICE_REQUESTS_ENABLED=false',
        '--workdir', '/project/src', $appImage
    ) + $Command
    Invoke-Docker -Arguments $arguments
}

Assert-CleanScope
$createdNetwork = $false
$createdDatabase = $false
$createdVolume = $false
$failed = $null
try {
    Invoke-Docker -Arguments @('network', 'create', '--internal', '--label', "nestakada.scope=$scope", $network)
    $createdNetwork = $true
    $createdName = @(
        Invoke-DockerOutput -Arguments @(
            'volume', 'create', '--label', "nestakada.scope=$scope",
            '--label', "nestakada.run=$runToken", $volume
        )
    )
    $createdVolume = $true
    if ($createdName.Count -ne 1 -or $createdName[0] -ne $volume) {
        throw 'CORE18_VOLUME_CREATE_AMBIGUOUS'
    }
    $createdOwner = @(
        Invoke-DockerOutput -Arguments @(
            'volume', 'inspect', '--format', '{{index .Labels "nestakada.run"}}', $volume
        )
    )
    if ($createdOwner.Count -ne 1 -or $createdOwner[0] -ne $runToken) {
        throw 'CORE18_VOLUME_OWNERSHIP_AMBIGUOUS'
    }
    Invoke-Docker -Arguments @(
        'run', '--detach', '--name', $database, '--network', $network, '--network-alias', 'core18-db',
        '--label', "nestakada.scope=$scope", '--read-only', '--cap-drop', 'ALL',
        '--cap-add', 'CHOWN', '--cap-add', 'DAC_OVERRIDE', '--cap-add', 'FOWNER',
        '--cap-add', 'SETGID', '--cap-add', 'SETUID',
        '--security-opt', 'no-new-privileges:true', '--mount',
        "type=volume,source=$volume,target=/var/lib/postgresql",
        '--tmpfs', '/var/run/postgresql:rw,nosuid,nodev,noexec,size=16m,uid=999,gid=999,mode=3775',
        '--tmpfs', '/tmp:rw,nosuid,nodev,noexec,size=32m,mode=1777',
        '--env', 'POSTGRES_DB=postgres', '--env', 'POSTGRES_USER=postgres',
        '--env', 'POSTGRES_PASSWORD=core18-synthetic-only', $postgresImage,
        'postgres', '-c', 'listen_addresses=*', '-c', 'log_statement=none',
        '-c', 'log_min_error_statement=panic', '-c', 'max_connections=30'
    )
    $createdDatabase = $true
    $ready = $false
    foreach ($attempt in 1..30) {
        & docker exec $database pg_isready -U postgres -d postgres *> $null
        if ($LASTEXITCODE -eq 0) { $ready = $true; break }
        Start-Sleep -Seconds 1
    }
    if (-not $ready) {
        & docker logs --tail 80 $database
        throw 'CORE18_POSTGRES_NOT_READY'
    }

    Invoke-App -Command @('python', 'manage.py', 'check')
    Invoke-App -Command @('python', 'manage.py', 'makemigrations', '--check', '--dry-run')
    Invoke-App -Command @(
        'python', 'manage.py', 'test', 'modules.service_requests', 'fitness',
        'modules.pages.tests.test_public_home', 'rebuild3_importer.tests.test_runtime_target',
        '--noinput', '--verbosity', '1'
    )
    Invoke-Docker -Arguments @(
        'run', '--rm', '--name', ('nestakada-core18-diagnostic-' + [guid]::NewGuid().ToString('N')),
        '--label', "nestakada.scope=$scope", '--network', 'none', '--read-only', '--cap-drop', 'ALL',
        '--security-opt', 'no-new-privileges:true', '--user', '10001:10001',
        '--tmpfs', '/tmp:rw,nosuid,nodev,noexec,size=64m,uid=10001,gid=10001,mode=1777',
        '--mount', "type=bind,source=$tools,target=/tools,readonly", '--entrypoint', 'python',
        $appImage, '/tools/test_rebuild7_generation_diagnostic.py'
    )
    Write-Output 'CORE18_RUNTIME_TESTS_OK'
}
catch {
    $failed = $_
}
finally {
    if ($createdDatabase) {
        & docker rm --force $database *> $null
        if ($LASTEXITCODE -ne 0) { $failed = 'CORE18_DATABASE_CLEANUP_FAILED' }
    }
    if ($createdVolume) {
        $cleanupOwner = @(& docker volume inspect --format '{{index .Labels "nestakada.run"}}' $volume)
        if ($LASTEXITCODE -ne 0 -or $cleanupOwner.Count -ne 1 -or $cleanupOwner[0] -ne $runToken) {
            $failed = 'CORE18_VOLUME_OWNERSHIP_AMBIGUOUS'
        }
        else {
            & docker volume rm --force $volume *> $null
            if ($LASTEXITCODE -ne 0) { $failed = 'CORE18_VOLUME_CLEANUP_FAILED' }
        }
    }
    if ($createdNetwork) {
        & docker network rm $network *> $null
        if ($LASTEXITCODE -ne 0) { $failed = 'CORE18_NETWORK_CLEANUP_FAILED' }
    }
}

Assert-CleanScope
Write-Output 'CORE18_RUNTIME_CLEANUP_OK containers=0 networks=0 volumes=0 staging=0'
if ($null -ne $failed) { throw $failed }
