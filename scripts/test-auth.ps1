# D-321 exclusive local authentication fixture; no VPS or production connections.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$root = Join-Path $repo 'work/foundation/test'
$fixture = Join-Path $root 'auth'
$manifest = Get-Content -Raw -LiteralPath (Join-Path $root 'manifest.json') | ConvertFrom-Json
if (!$manifest.active -or $manifest.environment -ne 'test' -or $manifest.composeProject -ne 'nestakada-foundation-test') { throw 'Active isolated test environment required.' }
$project = 'nestakada-foundation-test'
$compose = Join-Path $repo 'environment/foundation/compose.yaml'
$composeEnv = Join-Path $root 'compose.env'
$override = Join-Path $fixture 'compose.override.yaml'
$runner = Join-Path $fixture 'runner'
$clock = Join-Path $fixture 'clock'
$utf8 = New-Object Text.UTF8Encoding($false)
function Invoke-AuthDocker {
    param([string[]]$Arguments)
    $result = & docker.exe @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Authentication fixture Docker operation failed: $($Arguments[0])" }
    return $result
}
function Invoke-AuthCompose {
    param([string[]]$Arguments)
    Invoke-AuthDocker (@('compose','--env-file',$composeEnv,'-p',$project,'-f',$compose,'-f',$override) + $Arguments)
}
foreach ($port in @(8768,8769,8770)) {
    if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) { throw "Auth fixture port $port is occupied." }
}
foreach ($name in @('nestakada-auth-source-a','nestakada-auth-source-b')) {
    if (@(Invoke-AuthDocker @('ps','-aq','--filter',"name=^/$name$"))) { throw 'Existing auth fixture container requires explicit inspection before retry.' }
}
foreach ($directory in @($fixture,$runner,$clock)) {
    New-Item -ItemType Directory -Force -Path $directory | Out-Null
    if ((Get-Item -LiteralPath $directory).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Auth fixture reparse point rejected.' }
}
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$acl = [IO.Directory]::GetAccessControl($runner, [Security.AccessControl.AccessControlSections]::Access)
$acl.SetAccessRuleProtection($true,$false)
foreach ($rule in @($acl.Access)) { $acl.RemoveAccessRuleSpecific($rule) }
foreach ($sid in @($identity.User,(New-Object Security.Principal.SecurityIdentifier('S-1-5-18')))) {
    $acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule($sid,'FullControl','ContainerInherit,ObjectInherit','None','Allow')))
}
[IO.Directory]::SetAccessControl($runner, $acl)
$bytes = New-Object byte[] 48
$rng = [Security.Cryptography.RandomNumberGenerator]::Create()
try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
$token = [BitConverter]::ToString($bytes).Replace('-','').ToLowerInvariant()
[IO.File]::WriteAllText((Join-Path $runner 'control.json'),(@{origin='http://host.docker.internal:8770';token=$token}|ConvertTo-Json),$utf8)
[IO.File]::WriteAllText((Join-Path $clock 'clock.json'),(@{now=[DateTime]::UtcNow.ToString('o')}|ConvertTo-Json),$utf8)
$clockPath = $clock.Replace('\','/')
[IO.File]::WriteAllText($override,@"
services:
  app:
    environment:
      DJANGO_SETTINGS_MODULE: estakada.settings.auth_isolated
    volumes:
      - type: bind
        source: '$clockPath'
        target: /run/auth-fixture
        read_only: true
"@,$utf8)
$lock = Get-Content -Raw -LiteralPath (Join-Path $repo 'environment/foundation/runtime-images.lock.json') | ConvertFrom-Json
$image = ($lock.images | Where-Object component -eq 'local-ingress').reference
if ($lock.approvedBy -ne 'D-315' -or $image -ne 'sha256:a3b293bbab17bfd78d82d2392240d3d351501fba538ab82de1595b1d28d0d646') { throw 'Approved source-proxy image lock changed.' }
$config = Join-Path $repo 'environment/foundation/auth-source-nginx.conf'
$controller = $null
$created = New-Object 'System.Collections.Generic.List[string]'
$previousBase = $env:ESTAKADA_TEST_BASE_URL
$previousAuth = $env:ESTAKADA_AUTH_FIXTURE_DIRECTORY
try {
    Invoke-AuthCompose @('up','-d','--no-deps','--no-build','--pull','never','--force-recreate','app') | Out-Null
    Invoke-AuthCompose @('up','-d','--no-deps','--no-build','--pull','never','--force-recreate','ingress') | Out-Null
    foreach ($source in @(@{name='a';port=8768},@{name='b';port=8769})) {
        $name = "nestakada-auth-source-$($source.name)"
        Invoke-AuthDocker @('run','-d','--pull=never','--name',$name,'--label','nestakada.scope=auth-fixture-test',
            '--network','nestakada-foundation-test-ingress','--publish',"127.0.0.1:$($source.port):8080",'--user','101:101',
            '--read-only','--cap-drop=ALL','--security-opt=no-new-privileges:true','--memory=128m','--cpus=0.25','--pids-limit=64',
            '--tmpfs','/tmp:rw,nosuid,nodev,noexec,size=16m,uid=101,gid=101,mode=1777',
            '--mount',"type=bind,source=$config,target=/fixture/nginx.conf,readonly",'--entrypoint','nginx',$image,
            '-c','/fixture/nginx.conf','-g','daemon off;') | Out-Null
        $created.Add($name)
    }
    $node = (Get-Command node -ErrorAction Stop).Source
    $controllerScript = Join-Path $repo 'tools/auth-fixture-controller.mjs'
    $controller = Start-Process -FilePath $node -ArgumentList @($controllerScript) -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $fixture 'controller.stdout') -RedirectStandardError (Join-Path $fixture 'controller.stderr')
    $ready=$false
    for($attempt=0;$attempt -lt 40;$attempt++) {
        if($controller.HasExited) { throw 'Auth fixture controller exited; inspect its bounded local diagnostic.' }
        try { $client=New-Object Net.Sockets.TcpClient; $client.Connect('127.0.0.1',8770); $client.Close(); $ready=$true } catch {}
        if($ready){break};Start-Sleep -Milliseconds 250
    }
    if(!$ready) { throw 'Auth fixture controller did not become ready.' }
    $env:ESTAKADA_TEST_BASE_URL='http://host.docker.internal:8767'
    $env:ESTAKADA_AUTH_FIXTURE_DIRECTORY=$runner
    & (Join-Path $repo 'acceptance/run-container.ps1') -Mode auth-login
    if($LASTEXITCODE -ne 0) { throw 'Real authentication acceptance failed.' }
} finally {
    $env:ESTAKADA_TEST_BASE_URL=$previousBase
    $env:ESTAKADA_AUTH_FIXTURE_DIRECTORY=$previousAuth
    $cleanupFailure = $null
    if($controller -and !$controller.HasExited) {
        try {
            $statePath=Join-Path $fixture 'controller-state.json'
            if(Test-Path -LiteralPath $statePath) {
                $state=Get-Content -Raw -LiteralPath $statePath | ConvertFrom-Json
                if($state.controllerPid -eq $controller.Id -and $state.runId) {
                    $nonce=([guid]::NewGuid().ToString('N')+[guid]::NewGuid().ToString('N')).Substring(0,48)
                    $close=@{protocol='estakada-fixture-v1';nonce=$nonce;kind='close';runId=$state.runId;targetOrigin='http://host.docker.internal:8767'}|ConvertTo-Json
                    Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8770/control' -Method Post -ContentType 'application/json' -Headers @{Authorization="Bearer $token"} -Body $close -TimeoutSec 10 | Out-Null
                }
            }
        } catch { $cleanupFailure='Owned auth fixture cleanup failed; users preserved for explicit investigation.' }
    }
    if($controller -and !$controller.HasExited) { $controller.Kill(); $controller.WaitForExit(5000) | Out-Null }
    foreach($name in $created) {
        $actual=(Invoke-AuthDocker @('inspect',$name)|ConvertFrom-Json)[0]
        if($actual.Config.Labels.'nestakada.scope' -ne 'auth-fixture-test') { throw 'Refusing cleanup of foreign auth container.' }
        Invoke-AuthDocker @('rm','-f',$name) | Out-Null
    }
    # Restore the ordinary local profile and remove the fixture clock mount by recreation.
    Invoke-AuthDocker @('compose','--env-file',$composeEnv,'-p',$project,'-f',$compose,'up','-d','--no-deps','--no-build','--pull','never','--force-recreate','app') | Out-Null
    Invoke-AuthDocker @('compose','--env-file',$composeEnv,'-p',$project,'-f',$compose,'up','-d','--no-deps','--no-build','--pull','never','--force-recreate','ingress') | Out-Null
    if($cleanupFailure) { throw $cleanupFailure }
}
