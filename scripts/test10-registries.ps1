[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$bindingsPath = Join-Path $repo 'acceptance/test10a-bindings.json'
$payloadsPath = Join-Path $repo 'acceptance/test10a-payloads.json'
$observersPath = Join-Path $repo 'acceptance/test10a-observers.json'
$utf8 = New-Object Text.UTF8Encoding($false)
$failures = New-Object Collections.Generic.List[string]
$assertions = 0

function Assert-T10([bool]$Condition, [string]$Name) {
    $script:assertions++
    if (!$Condition) { $script:failures.Add($Name) }
}
function Get-T10Sha256([string]$Value) {
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash($utf8.GetBytes($Value)))).Replace('-','').ToLowerInvariant() }
    finally { $sha.Dispose() }
}
function Assert-T10ExactArray($Actual, [string[]]$Expected, [string]$Name) {
    Assert-T10 (@($Actual).Count -eq $Expected.Count) ($Name + '-count')
    if (@($Actual).Count -eq $Expected.Count) {
        Assert-T10 ((@($Actual) -join "`n") -ceq ($Expected -join "`n")) ($Name + '-order')
    }
}

foreach ($path in @($bindingsPath,$payloadsPath,$observersPath)) {
    Assert-T10 (Test-Path -LiteralPath $path -PathType Leaf) ('file-' + [IO.Path]::GetFileName($path))
    if (Test-Path -LiteralPath $path -PathType Leaf) {
        Assert-T10 (-not ((Get-Item -LiteralPath $path).Attributes -band [IO.FileAttributes]::ReparsePoint)) `
            ('ordinary-' + [IO.Path]::GetFileName($path))
    }
}
if ($failures.Count) { throw ('TEST10_REGISTRY_STATIC_FAILED: ' + ($failures -join ',')) }

$bindings = Get-Content -Raw -Encoding UTF8 -LiteralPath $bindingsPath | ConvertFrom-Json
$payloads = Get-Content -Raw -Encoding UTF8 -LiteralPath $payloadsPath | ConvertFrom-Json
$observers = Get-Content -Raw -Encoding UTF8 -LiteralPath $observersPath | ConvertFrom-Json
Assert-T10 ($bindings.schema -ceq 'test10a-binding-registry-v1') 'binding-schema'
Assert-T10 ($payloads.schema -ceq 'test10a-payload-registry-v1') 'payload-schema'
Assert-T10 ($observers.schema -ceq 'test10a-observer-registry-v1') 'observer-schema'
Assert-T10 ($bindings.registryReady -eq $false -and $bindings.bindingStatus -ceq 'unbound') 'binding-readiness-honest'
Assert-T10 ($observers.registryReady -eq $false) 'observer-readiness-honest'

$caseIds = @('AC-013','AC-014','AC-015','AC-021','AC-022','AC-023','AC-DTL-004','AC-DTL-006','AC-DTL-018')
$scenarioIds = @('T10C-AC013','T10C-AC014','T10C-AC015','T10C-AC021','T10C-AC022','T10C-AC023','T10C-DTL004','T10C-DTL006','T10C-DTL018')
Assert-T10ExactArray $bindings.acceptanceCaseIds $caseIds 'acceptance-cases'
Assert-T10ExactArray $bindings.runScenarioIds $scenarioIds 'scenario-ids'
Assert-T10ExactArray $bindings.scenarios.id $scenarioIds 'scenario-records'
Assert-T10ExactArray $bindings.scenarios.acceptance $caseIds 'scenario-acceptance-map'
$expectedActions = @(
    @('UI-013-SAFE','HTTP-013-ACTIVE','HTTP-013-HEADER','HTTP-013-FOOTER','UI-013-POSITIVE'),
    @('UI-014-OWNER-RESET','HTTP-014-OLD-SESSIONS','HTTP-014-SELF-CHANGE','HTTP-014-SELF-RECOVERY','UI-014-NEW-LOGIN','OBS-014-SECRET-SINKS'),
    @('UI-015-UNSAVED','HTTP-015-IDLE1801','HTTP-015-ABS43201','UI-015-RELOGIN','HTTP-015-OTHER-DENY','UI-015-EXPLICIT-SAVE','UI-015-OWNER-REVOKE','HTTP-015-REVOKED-DENY'),
    @('UI-021-HISTORY','UI-021-OWNER-CONTROL','HTTP-021-VISITOR','HTTP-021-S-OTHER','OBS-021-CACHE'),
    @('UI-022-COMPARE','UI-022-CANCEL','UI-022-STAGE','UI-022-SAVE','UI-022-OWNER-CONTROL','OBS-022-PROTECTED-UNCHANGED'),
    @('UI-023-INCOMPATIBLE','UI-023-COMPARE-BEFORE-REVOKE','UI-023-OWNER-REVOKE','UI-023-REVOKED','UI-023-COMPATIBLE-CONTROL'),
    @('UI-104-NORMALISE','P104-1M','P104-TEXT200K','P104-NODES20K','P104-DEPTH32','P104-ACTIVE-SET','UI-104-POSITIVE'),
    @('UI-106-SAFE-LINKS','P106-UNSAFE-SET','HTTP-106-PROTECTED-SET','OBS-106-CLIENT-NETWORK','OBS-106-SERVER-EGRESS','UI-106-POSITIVE'),
    @('UI-118-VALIDATION','UI-118-EXPIRY','UI-118-CONFLICT','OBS-118-BROWSER-STORAGE')
)
for ($index = 0; $index -lt $expectedActions.Count; $index++) {
    Assert-T10ExactArray $bindings.scenarios[$index].actions $expectedActions[$index] ('scenario-actions-' + $scenarioIds[$index])
}

$bindingIds = @($bindings.bindings.id)
$payloadIds = @($payloads.payloads.id)
$observerIds = @($observers.observers.id)
$expectedPayloadIds = @('P013-SAFE','P104-1M','P104-TEXT200K','P104-NODES20K','P104-DEPTH32','P104-ACTIVE-SET',
    'P106-SAFE-LINKS','P106-UNSAFE-SET','PBODY-RESET','PBODY-SELF-CHANGE','PBODY-LOGIN-OLD','PBODY-LOGIN-NEW',
    'PBODY-SAVE','PBODY-RESTORE-HISTORICAL','PBODY-RESTORE-INCOMPATIBLE','PBODY-REVOKE','PBODY-EDITOR-CANARY')
$expectedPayloadKinds = @('literal-html','boundary-pair','boundary-pair','boundary-pair','boundary-pair','literal-html-set',
    'literal-url-set','literal-url-set','request-template','request-template','request-template','request-template',
    'request-template','request-template','request-template','request-template','request-template')
Assert-T10ExactArray $payloadIds $expectedPayloadIds 'payload-order'
Assert-T10ExactArray $payloads.payloads.kind $expectedPayloadKinds 'payload-kinds'
Assert-T10 (($bindingIds | Sort-Object -Unique).Count -eq $bindingIds.Count) 'binding-ids-unique'
Assert-T10 (($payloadIds | Sort-Object -Unique).Count -eq $payloadIds.Count) 'payload-ids-unique'
Assert-T10 (($observerIds | Sort-Object -Unique).Count -eq $observerIds.Count) 'observer-ids-unique'

$allRefs = @($bindingIds + $payloadIds + $observerIds)
$scenarioRefs = @($bindings.scenarios | ForEach-Object {$_.actions})
Assert-T10 (@($scenarioRefs | Where-Object {$_ -cnotin $allRefs}).Count -eq 0) 'scenario-refs-known'
Assert-T10 (@($bindingIds | Where-Object {$_ -cnotin $scenarioRefs}).Count -eq 0) 'bindings-all-used'
Assert-T10 (@($observerIds | Where-Object {$_ -cnotin $scenarioRefs}).Count -eq 0) 'observers-all-used'
$usedPayloads = @($scenarioRefs + @($bindings.bindings.payload) + @($bindings.bindings.contentPayload))
Assert-T10 (@($payloadIds | Where-Object {$_ -cnotin $usedPayloads}).Count -eq 0) 'payloads-all-used'

$allowedRoute = '^/(manage/(pages/\{page\}/(edit/(check/|save/)?|versions/(\{version\}/)?)|employees/\{employee\}/(password|grants)/|login/|shared/(header|footer)/edit/save/)|test10/assigned/|header/|footer/)$'
$allowedActors = @('OWNER','S-EDIT','S-EDIT-OLD','S-EDIT-IDLE1801','S-EDIT-ABS43201','S-EDIT-EXPIRED','S-OTHER','S-REVOKED','VISITOR')
foreach ($binding in $bindings.bindings) {
    Assert-T10ExactArray $binding.PSObject.Properties.Name `
        @('id','kind','actor','route','method','payload','contentPayload','oracle','implementationStatus') `
        ('binding-schema-' + $binding.id)
    Assert-T10 ($binding.kind -cin @('ui','http')) ('binding-kind-' + $binding.id)
    Assert-T10 ($binding.actor -cin $allowedActors) ('binding-actor-' + $binding.id)
    Assert-T10 ($binding.method -cin @('GET','POST')) ('binding-method-' + $binding.id)
    Assert-T10 ([string]$binding.route -cmatch $allowedRoute) ('binding-route-' + $binding.id)
    Assert-T10 ([string]$binding.route -cnotmatch '[?#*]|\.\.\.') ('binding-route-closed-' + $binding.id)
    Assert-T10 ($binding.implementationStatus -ceq 'unbound') ('binding-status-' + $binding.id)
    Assert-T10 (-not [string]::IsNullOrWhiteSpace([string]$binding.oracle)) ('binding-oracle-' + $binding.id)
    if ($null -ne $binding.payload) {
        Assert-T10 ($binding.payload -cin $payloadIds) ('binding-payload-' + $binding.id)
    }
    if ($null -ne $binding.contentPayload) {
        Assert-T10 ($binding.contentPayload -cin $payloadIds) ('binding-content-payload-' + $binding.id)
    }
    if ($binding.method -ceq 'POST') {
        Assert-T10 ($null -ne $binding.payload) ('binding-post-body-' + $binding.id)
    }
}
$uiBindingIds = @($bindings.bindings | Where-Object {$_.kind -ceq 'ui'} | ForEach-Object {$_.id})
Assert-T10ExactArray $bindings.uiSteps.PSObject.Properties.Name $uiBindingIds 'ui-step-keys'
foreach ($id in $uiBindingIds) {
    $steps = @($bindings.uiSteps.$id)
    Assert-T10 ($steps.Count -gt 0) ('ui-steps-nonempty-' + $id)
    Assert-T10 (@($steps | Where-Object {$_ -cnotmatch '^[a-z][a-z-]*:[A-Za-z0-9.-]+$'}).Count -eq 0) ('ui-steps-closed-' + $id)
}

foreach ($payload in @($payloads.payloads | Where-Object {$_.kind -ceq 'boundary-pair'})) {
    if ($payload.generator -ceq 'repeat') {
        $exact = [string]$payload.unit * [int]$payload.exactCount
        $plusOne = [string]$payload.unit * [int]$payload.plusOneCount
    } elseif ($payload.generator -ceq 'nested') {
        $exact = ([string]$payload.open * [int]$payload.exactCount) + [string]$payload.text +
            ([string]$payload.close * [int]$payload.exactCount)
        $plusOne = ([string]$payload.open * [int]$payload.plusOneCount) + [string]$payload.text +
            ([string]$payload.close * [int]$payload.plusOneCount)
    } else {
        $failures.Add('payload-generator-' + $payload.id)
        continue
    }
    Assert-T10 ((Get-T10Sha256 $exact) -ceq $payload.exactSha256) ('payload-exact-hash-' + $payload.id)
    Assert-T10 ((Get-T10Sha256 $plusOne) -ceq $payload.plusOneSha256) ('payload-plus-one-hash-' + $payload.id)
}

foreach ($payload in @($payloads.payloads | Where-Object {$_.kind -cin @('literal-html','request-template')})) {
    Assert-T10 (-not [string]::IsNullOrEmpty([string]$payload.value)) ('payload-value-' + $payload.id)
    Assert-T10 ((Get-T10Sha256 ([string]$payload.value)) -ceq $payload.sha256) ('payload-hash-' + $payload.id)
    if ($payload.kind -ceq 'request-template') {
        Assert-T10 ($payload.contentType -ceq 'application/x-www-form-urlencoded') ('payload-content-type-' + $payload.id)
        Assert-T10 ([string]$payload.value -cnotmatch '(?i)(password|secret)=((?!\{)[^&]+)') ('payload-no-secret-value-' + $payload.id)
    }
}
$expectedTokens = @('{identifiers.page}','{identifiers.currentRevision}','{identifiers.historicalRevision}',
    '{identifiers.incompatibleRevision}','{identifiers.editUser}','{content.payload}')
$expectedReceiptPaths = @('summary.identifiers.page','summary.identifiers.currentRevision','summary.identifiers.historicalRevision',
    'summary.identifiers.incompatibleRevision','summary.identifiers.editUser','binding.contentPayload')
$expectedTokenTypes = @('uuid','uuid','uuid','uuid','positive-int','canonical-registry-bytes')
Assert-T10ExactArray $payloads.placeholderBindings.token $expectedTokens 'placeholder-tokens'
Assert-T10ExactArray $payloads.placeholderBindings.receiptPath $expectedReceiptPaths 'placeholder-paths'
Assert-T10ExactArray $payloads.placeholderBindings.type $expectedTokenTypes 'placeholder-types'
Assert-T10ExactArray $payloads.privateReferences.label @('OLD-SYNTHETIC-SECRET','NEW-SYNTHETIC-SECRET') 'private-reference-labels'
Assert-T10ExactArray $payloads.privateReferences.source @('private.passwords.S-EDIT','run-private.generatedNextPassword.S-EDIT') 'private-reference-sources'
foreach ($payload in @($payloads.payloads | Where-Object {$_.kind -ceq 'request-template'})) {
    $tokens = @([regex]::Matches([string]$payload.value,'\{[^}]+\}') | ForEach-Object {$_.Value})
    Assert-T10 (@($tokens | Where-Object {$_ -cnotin $expectedTokens}).Count -eq 0) ('payload-placeholders-closed-' + $payload.id)
}
foreach ($payload in @($payloads.payloads | Where-Object {$_.kind -cin @('literal-html-set','literal-url-set')})) {
    Assert-T10 (@($payload.values).Count -gt 0) ('payload-set-nonempty-' + $payload.id)
    Assert-T10 (@($payload.values.id | Sort-Object -Unique).Count -eq @($payload.values).Count) ('payload-set-ids-' + $payload.id)
    foreach ($value in $payload.values) {
        Assert-T10 (-not [string]::IsNullOrEmpty([string]$value.value)) ('payload-set-value-' + $payload.id + '-' + $value.id)
        Assert-T10 ((Get-T10Sha256 ([string]$value.value)) -ceq $value.sha256) ('payload-set-hash-' + $payload.id + '-' + $value.id)
    }
}
$expectedSetMemberIds = @{
    'P104-ACTIVE-SET' = @('event','script','iframe','css-url','css-position','template-expression','template-tag','template-comment')
    'P106-SAFE-LINKS' = @('local','http','https')
    'P106-UNSAFE-SET' = @('javascript','mixed-case','entity','encoded-control','data','file','vbscript','protocol-relative','userinfo','backslash')
}
foreach ($id in $expectedSetMemberIds.Keys) {
    $payload = @($payloads.payloads | Where-Object {$_.id -ceq $id})[0]
    Assert-T10ExactArray $payload.values.id $expectedSetMemberIds[$id] ('payload-set-members-' + $id)
}

$expectedObserverIds = @('OBS-014-SECRET-SINKS','OBS-021-CACHE','OBS-022-PROTECTED-UNCHANGED','OBS-106-CLIENT-NETWORK','OBS-106-SERVER-EGRESS','OBS-118-BROWSER-STORAGE')
$expectedObserverInputs = @('UI-014-OWNER-RESET','HTTP-021-S-OTHER','UI-022-SAVE','UI-106-SAFE-LINKS','HTTP-106-PROTECTED-SET','UI-118-CONFLICT')
Assert-T10ExactArray $observerIds $expectedObserverIds 'observer-order'
Assert-T10ExactArray $observers.observers.inputBinding $expectedObserverInputs 'observer-inputs'
Assert-T10 (@($observers.observers | Where-Object {$_.implementationStatus -cne 'unbound'}).Count -eq 0) 'observers-all-unbound'
$expectedObserverSinks = @(
    @('audit','application-log','response','browser-view'),
    @('denial-response-cache-policy'),
    @('url','parent','published','grants','stable','employee-protected-fields'),
    @('actual-actor-tab-http','actual-actor-tab-websocket'),
    @('isolated-stand-server-egress'),
    @('location-url','localStorage','sessionStorage')
)
$expectedObserverOutputs = @(
    @('status','sinkSetSha256','complete','canaryPresentBySink'),
    @('status','class','cachePrivate','noStore'),
    @('status','complete','unchangedByField'),
    @('status','complete','requests.method','requests.pathWithoutQueryOrFragment','requests.statusClass','requests.destinationOrigin'),
    @('status','serverFetchObserved'),
    @('status','complete','urlContainsCanary','localStorageContainsCanary','sessionStorageContainsCanary')
)
$expectedObserverSemantics = @(
    'incomplete-or-drift=BLOCKED; any-present=FAIL; complete-and-all-false=PASS',
    'gap=BLOCKED; unexpected-access-or-false-flag=FAIL; denial-and-both-true=PASS',
    'gap=BLOCKED; any-changed=FAIL; complete-and-all-unchanged=PASS',
    'incomplete=BLOCKED; external-request=FAIL; complete-and-zero-external=PASS',
    'unavailable-or-drift=BLOCKED; true=FAIL; false=PASS',
    'missing-scope=BLOCKED; any-present=FAIL; complete-and-all-false=PASS'
)
foreach ($observer in $observers.observers) {
    $observerIndex = [Array]::IndexOf($expectedObserverIds,[string]$observer.id)
    Assert-T10 ($null -eq $observer.source) ('observer-source-unbound-' + $observer.id)
    Assert-T10ExactArray $observer.sinkSet $expectedObserverSinks[$observerIndex] ('observer-sinks-' + $observer.id)
    Assert-T10ExactArray $observer.output $expectedObserverOutputs[$observerIndex] ('observer-output-' + $observer.id)
    Assert-T10 ([string]$observer.semantics -ceq $expectedObserverSemantics[$observerIndex]) ('observer-semantics-' + $observer.id)
}
$memory = @($observers.observers | Where-Object {$_.id -ceq 'OBS-118-BROWSER-STORAGE'})
Assert-T10 ($memory.Count -eq 1 -and $memory[0].candidateSource -ceq
    'acceptance/browser-memory.js#inspectBrowserPersistence') 'memory-observer-candidate'

if ($failures.Count) { throw ('TEST10_REGISTRY_STATIC_FAILED: ' + ($failures -join ',')) }
[ordered]@{
    schema = 'test10a-registry-static-v1'
    status = 'PASS'
    assertions = $assertions
    registryReady = $false
    unboundBindings = @($bindings.bindings | Where-Object {$_.implementationStatus -ceq 'unbound'}).Count
    unboundObservers = @($observers.observers | Where-Object {$_.implementationStatus -ceq 'unbound'}).Count
    bindingsSha256 = (Get-FileHash -LiteralPath $bindingsPath -Algorithm SHA256).Hash.ToLowerInvariant()
    payloadRegistrySha256 = (Get-FileHash -LiteralPath $payloadsPath -Algorithm SHA256).Hash.ToLowerInvariant()
    observerRegistrySha256 = (Get-FileHash -LiteralPath $observersPath -Algorithm SHA256).Hash.ToLowerInvariant()
    dockerCalled = $false
} | ConvertTo-Json -Compress
