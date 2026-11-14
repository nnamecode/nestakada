[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest

$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$bindingsPath=Join-Path $repo 'acceptance/test10a-bindings.json'
$payloadsPath=Join-Path $repo 'acceptance/test10a-payloads.json'
$observersPath=Join-Path $repo 'acceptance/test10a-observers.json'
$utf8=New-Object Text.UTF8Encoding($false)
$failures=New-Object Collections.Generic.List[string]
$assertions=0
function Assert-T10([bool]$condition,[string]$name){$script:assertions++;if(!$condition){$script:failures.Add($name)}}
function Sha-T10([string]$value){$sha=[Security.Cryptography.SHA256]::Create();try{([BitConverter]::ToString($sha.ComputeHash($utf8.GetBytes($value)))).Replace('-','').ToLowerInvariant()}finally{$sha.Dispose()}}
function Exact-T10($actual,[string[]]$expected,[string]$name){$a=@($actual);Assert-T10 ($a.Count -eq $expected.Count) ($name+'-count');if($a.Count -eq $expected.Count){Assert-T10 (($a -join "`n") -ceq ($expected -join "`n")) ($name+'-order')}}
function Props-T10($value,[string[]]$expected,[string]$name){Exact-T10 $value.PSObject.Properties.Name $expected $name}
function Field-T10($value,[string]$name){$property=$value.PSObject.Properties[$name];if($null -eq $property -or $null -eq $property.Value){'<null>'}else{[string]$property.Value}}
function RequestSignature-T10($step){(@('actor','sessionSource','csrfSource','method','route','body','content'|ForEach-Object{Field-T10 $step $_}) -join '|')}
function NonRequestSignature-T10($step){(@('actor','sessionSource','action','content','transition','sourceContext','targetContext','observer'|ForEach-Object{Field-T10 $step $_}) -join '|')}
function PinSequence-T10([string]$bindingId,[string[]]$types,[string[]]$stepIds,[string[]]$expected){
    $binding=@($b.bindings|Where-Object{$_.id -ceq $bindingId})[0]
    Exact-T10 $binding.steps.type $types ('pin-types-'+$bindingId)
    Exact-T10 $binding.steps.id $stepIds ('pin-step-ids-'+$bindingId)
    Exact-T10 $binding.steps.expected $expected ('pin-expected-'+$bindingId)
}
function PinRequests-T10([string]$bindingId,[string[]]$signatures){
    $binding=@($b.bindings|Where-Object{$_.id -ceq $bindingId})[0]
    Exact-T10 @($binding.steps|Where-Object{$_.type -ceq 'request'}|ForEach-Object{RequestSignature-T10 $_}) $signatures ('pin-requests-'+$bindingId)
}
function JsonString-T10([string]$value){
    $builder=New-Object Text.StringBuilder
    [void]$builder.Append('"')
    foreach($char in $value.ToCharArray()){
        $code=[int][char]$char
        if($char -eq '"'){[void]$builder.Append('\"')}
        elseif($code -eq 92){[void]$builder.Append('\\')}
        elseif($code -eq 8){[void]$builder.Append('\b')}
        elseif($code -eq 9){[void]$builder.Append('\t')}
        elseif($code -eq 10){[void]$builder.Append('\n')}
        elseif($code -eq 12){[void]$builder.Append('\f')}
        elseif($code -eq 13){[void]$builder.Append('\r')}
        elseif($code -lt 32){[void]$builder.Append(('\u{0:x4}' -f $code))}
        else{[void]$builder.Append($char)}
    }
    [void]$builder.Append('"');$builder.ToString()
}

foreach($path in @($bindingsPath,$payloadsPath,$observersPath)){
    Assert-T10 (Test-Path -LiteralPath $path -PathType Leaf) ('file-'+[IO.Path]::GetFileName($path))
    if(Test-Path -LiteralPath $path -PathType Leaf){Assert-T10 (-not ((Get-Item -LiteralPath $path).Attributes -band [IO.FileAttributes]::ReparsePoint)) ('ordinary-'+[IO.Path]::GetFileName($path))}
}
if($failures.Count){throw ('TEST10_REGISTRY_STATIC_FAILED: '+($failures -join ','))}
$b=Get-Content -Raw -Encoding UTF8 -LiteralPath $bindingsPath|ConvertFrom-Json
$p=Get-Content -Raw -Encoding UTF8 -LiteralPath $payloadsPath|ConvertFrom-Json
$o=Get-Content -Raw -Encoding UTF8 -LiteralPath $observersPath|ConvertFrom-Json
Assert-T10 ($b.schema -ceq 'test10a-binding-registry-v2') 'binding-schema'
Assert-T10 ($p.schema -ceq 'test10a-payload-registry-v2') 'payload-schema'
Assert-T10 ($o.schema -ceq 'test10a-observer-registry-v2') 'observer-schema'
Assert-T10 ($b.registryReady -eq $false -and $b.bindingStatus -ceq 'unbound' -and $o.registryReady -eq $false) 'readiness-closed'

$caseIds=@('AC-013','AC-014','AC-015','AC-021','AC-022','AC-023','AC-DTL-004','AC-DTL-006','AC-DTL-018')
$scenarioIds=@('T10C-AC013','T10C-AC014','T10C-AC015','T10C-AC021','T10C-AC022','T10C-AC023','T10C-DTL004','T10C-DTL006','T10C-DTL018')
Exact-T10 $b.acceptanceCaseIds $caseIds 'case-ids';Exact-T10 $b.runScenarioIds $scenarioIds 'scenario-ids'
Exact-T10 $b.scenarios.id $scenarioIds 'scenario-records';Exact-T10 $b.scenarios.acceptance $caseIds 'scenario-map'
$bindingIds=@($b.bindings.id)
Assert-T10 ($bindingIds.Count -eq 40 -and @($bindingIds|Sort-Object -Unique).Count -eq 40) 'bindings-40-unique'
Assert-T10 (@($b.bindings|Where-Object{$_.implementationStatus -cne 'unbound'}).Count -eq 0) 'bindings-unbound'
$orderNumbers=@(1,2,3,4,5,12,13,6,7,9,10,8,11,14,15)+(18..28)+(32..40)+@(29,30,31,16,17)
$expectedOrder=@($orderNumbers|ForEach-Object{$bindingIds[$_-1]})
Exact-T10 $b.executionBindingOrder $expectedOrder 'execution-order'
Assert-T10 (@($b.executionBindingOrder|Sort-Object -Unique).Count -eq 40) 'execution-order-unique'
Exact-T10 $b.bindings.executionKind @('request','request','request','request','ui-sequence','request','request','request','request','request','ui-sequence','request','request','request','request','evidence-reference','request','ui-sequence','request','request','request','request','request','ui-sequence','ui-sequence','binding-reference','ui-sequence','request','request','request','request','ui-sequence','ui-sequence','ui-sequence','ui-sequence','request','ui-sequence','request','ui-sequence','ui-sequence') 'binding-execution-kinds'
Exact-T10 $b.bindings.oracle @('ordinary-published-page-has-real-shared-header-footer','deny-without-mutation','not-a-page-and-no-shared-component-content','not-a-page-and-no-shared-component-content','accepted-and-published','owner-reset-accepted','deny-without-private-canary','deny-without-auth-mutation','old-secret-denied-without-recovery','new-login-accepted','unsaved-input-visible-only-in-tab','deny-without-mutation','deny-without-mutation','login-accepted','deny-without-closed-data','grant-revoked-before-next-request','deny-without-closed-data','explicit-save-only','all-version-kinds-visible','owner-history-control','deny','deny','compare-without-mutation','cancel-without-mutation','direct-role-limited-restore-one-revision','direct-restore-creates-version','owner-protected-control','deny-all-or-nothing','historical-comparison-open-before-revoke','grant-revoked-after-comparison','deny-all-or-nothing-after-revoke','fresh-compatible-role-limited-restore-one-revision','safe-structure-normalised','accepted-and-versioned','allowed-links-preserved-with-noopener','deny-without-mutation','accepted-and-versioned','validation-retains-tab-only-input','expiry-retains-tab-only-input','conflict-retains-tab-only-input') 'binding-oracles'

$contentIds=@('P013-SAFE','P104-1M','P104-TEXT200K','P104-NODES20K','P104-DEPTH32','P104-ACTIVE-SET','P106-SAFE-LINKS','P106-UNSAFE-SET')
$requestIds=@('REQ-PASSWORD-NEW','REQ-LOGIN-OLD','REQ-LOGIN-NEW','REQ-GRANT-REVOKE','REQ-EDITOR-CHECK','REQ-EDITOR-SAVE','REQ-RESTORE-PREPARE','REQ-RESTORE-APPLY')
$payloadIds=@($p.payloads.id);Exact-T10 $payloadIds @($contentIds+$requestIds) 'payload-order'
Assert-T10 (@($payloadIds|Sort-Object -Unique).Count -eq 16) 'payload-unique'
Props-T10 $p @('schema','encoding','canonicalJson','placeholderBindings','privateReferences','contentProjections','payloads') 'payload-root-props'
Assert-T10 ($p.encoding -ceq 'utf-8' -and $p.canonicalJson -eq $true) 'payload-root-contract'
$contentPayloads=@($p.payloads|Select-Object -First 8)
Exact-T10 $contentPayloads.kind @('literal-html','boundary-pair','boundary-pair','boundary-pair','boundary-pair','literal-html-set','literal-url-set','literal-url-set') 'content-kinds'
$p013=$contentPayloads[0];Props-T10 $p013 @('id','kind','value','sha256') 'content-props-P013-SAFE';Assert-T10 ($p013.sha256 -ceq 'd66dabef68b47f2352978324c3abf22c41195c392d16275c84580870f4b670b2') 'content-hash-P013-SAFE'
foreach($id in @('P104-1M','P104-TEXT200K','P104-NODES20K')){$payload=@($contentPayloads|Where-Object{$_.id -ceq $id})[0];Props-T10 $payload @('id','kind','generator','unit','exactCount','plusOneCount','exactSha256','plusOneSha256') ('content-props-'+$id)}
$depth=@($contentPayloads|Where-Object{$_.id -ceq 'P104-DEPTH32'})[0];Props-T10 $depth @('id','kind','generator','open','text','close','exactCount','plusOneCount','exactSha256','plusOneSha256') 'content-props-P104-DEPTH32'
$boundaries=@($contentPayloads|Where-Object{$_.kind -ceq 'boundary-pair'});Exact-T10 $boundaries.generator @('repeat','repeat','repeat','nested') 'boundary-generators';Exact-T10 $boundaries.exactCount @('1048576','200000','20000','32') 'boundary-exact-counts';Exact-T10 $boundaries.plusOneCount @('1048577','200001','20001','33') 'boundary-plus-counts';Exact-T10 $boundaries.exactSha256 @('9bc1b2a288b26af7257a36277ae3816a7d4f16e89c1e7e77d0a5c48bad62b360','2287d207f24a941ff3b56c04c8a25ad56b63e3023207b3bb5b4ac0c9869d74be','59b11a20ca54e8cf93d7f3a63b5a8f53e08746cd5f65426f3bd34e7695b171c0','f74574570179c48db9370a608c185ec7d44c97d3421fc5f20735d8ad926c8227') 'boundary-exact-hashes';Exact-T10 $boundaries.plusOneSha256 @('4a3f0c0c213adea174f9a3d4c13177315b588bdb2e9c1012d3d0bf0453ca0f6a','299c0ddb1d4e35143ab7ea9f57c435d09dc425da1ad5d941c7028a234f4af719','4cda67289c705caf35ccddb9b939b69d520edeb55f3a48a21f4b7a3df8b14ee8','20e30a50796e2d3529855524a961ef0902bc794a20fe99f5c6b78bedaed117b0') 'boundary-plus-hashes'
$active=@($contentPayloads|Where-Object{$_.id -ceq 'P104-ACTIVE-SET'})[0];Props-T10 $active @('id','kind','values') 'content-props-P104-ACTIVE-SET';foreach($value in $active.values){Props-T10 $value @('id','value','sha256') ('active-value-props-'+$value.id)};Exact-T10 $active.values.id @('event','script','iframe','css-url','css-position','template-expression','template-tag','template-comment') 'active-value-ids';Exact-T10 $active.values.sha256 @('1831244310be8e144eaaae0b36334579cfbce2ac1983a5d7d7f67e867e3df2a0','f8854e0a8b8b6aad43c8c7998f1d52e18b2d81b9f84d6c334019170f144e803b','974bc2cfc9578d2cbaa9de57ad4601c948bff04f73e50fce67ce45ec3dcf1c1b','9f0d0f742d5fe7bbceaa05600b2df962922fb37d4e0374e00b06bf763a29b8d4','a6800b04c5d85a2d9ab399638dba513a8e54d5879c840f96add09f709c4d6ac1','f170251ff5dd7c2ac1a712d50c2d0c45a15d6d2977450f752c1208b6c855b0aa','bbc5b0eed5eccce7ed95e82a6e7c7bfd72d3108d930f690da57c0d002ece5dd2','a19c4898b68d95f0d181322c0f3386cbd7b79a13066f9bee50112d92bf13a3f2') 'active-value-hashes'
$safeLinks=@($contentPayloads|Where-Object{$_.id -ceq 'P106-SAFE-LINKS'})[0];$unsafeLinks=@($contentPayloads|Where-Object{$_.id -ceq 'P106-UNSAFE-SET'})[0];foreach($set in @($safeLinks,$unsafeLinks)){Props-T10 $set @('id','kind','values') ('content-props-'+$set.id);foreach($value in $set.values){Props-T10 $value @('id','value','sha256','projectedSha256') ('url-value-props-'+$set.id+'-'+$value.id)}}
Exact-T10 $safeLinks.values.id @('local','http','https') 'safe-link-ids';Exact-T10 $safeLinks.values.sha256 @('b8e3271456c332cdf4cd7816aae0394760221a6ab5d3d0af159682115557a418','b0ad8624a29d427174a0160992bc2bb193920f6d416738f7abe26069aac866eb','eeee77d5cf89d69e82e7769536f54d4749494a7116bebf47a6eaf9306d3041db') 'safe-link-hashes';Exact-T10 $safeLinks.values.projectedSha256 @('c17b0de65f50e78d7c129d805102fda96b158db44cf0f4367c1cf8fcb62853ec','b3e7637b3f38e60151e6e49816177e3fad5d3f403f3fefa1ffbcecaa5c42d7d4','901c76c1cf17242eb7c6f6b2302848078ad072cb7ad630d8b08b2f2e080d8c5a') 'safe-link-projected-hashes'
Exact-T10 $unsafeLinks.values.id @('javascript','mixed-case','entity','encoded-control','data','file','vbscript','protocol-relative','userinfo','backslash') 'unsafe-link-ids';Exact-T10 $unsafeLinks.values.sha256 @('2315ebacfe4d1cf327bad8a909550deefe37209297df22db30b256ab3873f6bb','eef20187987990b32a2e67f9d2afa5e765c32701a504a9568415a3db42602365','622a412f0af2d78e58057a5c2f8dd91c6c4fcee736e75f5b21fa736bf4f2873e','b409f849683c1f002e1e9ca29b7670c037f565dfb130aa2803eb30185af3a044','245af083e6e132ce8dcaf45babef4119f94d9385ebb4b68054ab796752d0d2c1','03192780d4146e93b9b7723c70a6ba168e41d05d364ba1b436da942feaecd279','05a03b3d8db1fc27dea8116a2e8e12daceb8fbe7a2b1d48f33d37b2bbe1e5f05','aa371903c422d092dad16f13ac65939f966b8652508112c92e7e81bd12822e89','4e3c8e31f38d3924ff43f00d725820fa3dd3c17354676f15becf55b28242c660','33372a9f5a1dd3420f108d9d0bcac4152ad21fcfce7558dcdac1d41f1b9c6155') 'unsafe-link-hashes';Exact-T10 $unsafeLinks.values.projectedSha256 @('a1927edad2fee8dec38d598e0b5e280593bdbe5dbed5bdf4e83d210cabca939d','cfe809c50ff01f91af71cf0036f647dab8b31f075bffe3615804a16c4ade9f72','79cabf8d533b97ab2d319b727419d6440d804de93a207ffc164cfc0132329d71','2f9aa81840dc3efe648dbed7547c735f4aabd9a996e44118fbe94919be91307a','3c6c4f4b691ac734b535936b83aa765fc9f7cb1590f9ffd80184dfd707a5e50c','c57e3350df0f5a1571812f0fd0a4a9b331de828427d6b2e3ba0ea04e90ecda00','7be0025395df588d38a83f0653ad9721c047442ebf53f5c5eff791f805532488','1c858126c7a2ffec84adeff06fe8954d4b398943a1fdbfb9c3678761c73f6879','95291c1c29472ef53b409368c5f323f16a30e3062aa3e124681351be62ea61b2','eb667ee7f5735367855247be894e1a17ec5ba36b3b2b82a606792de131cf535e') 'unsafe-link-projected-hashes'
$allowedActors=@('OWNER','S-EDIT','S-EDIT-OLD','S-EDIT-IDLE1801','S-EDIT-ABS43201','S-EDIT-EXPIRED','S-OTHER','S-REVOKED','VISITOR')
$allowedRoutes='^/(manage/(pages/\{page\}/(edit/(check/|save/)?|versions/(\{version\}/(compare/|restore/(prepare|apply)/)?)?)|employees/\{employee\}/(password|grants)/|login/)|test10/assigned/|header/|footer/)$'
$consumed=New-Object Collections.Generic.List[string]
$revokeRequests=0
foreach($binding in $b.bindings){
    Props-T10 $binding @('id','executionKind','steps','oracle','implementationStatus') ('binding-props-'+$binding.id)
    Assert-T10 ($binding.executionKind -cin @('request','ui-sequence','binding-reference','evidence-reference')) ('binding-kind-'+$binding.id)
    Assert-T10 (@($binding.steps).Count -gt 0) ('binding-steps-'+$binding.id)
    $stepIds=@($binding.steps.id);Assert-T10 (@($stepIds|Sort-Object -Unique).Count -eq $stepIds.Count) ('step-ids-'+$binding.id)
    Assert-T10 (@($binding.steps|Where-Object{$_.expected -isnot [string]}).Count -eq 0) ('scalar-expected-'+$binding.id)
    switch([string]$binding.executionKind){
        'request' {Assert-T10 (@($binding.steps|Where-Object{$_.type -cne 'request'}).Count -eq 0) ('kind-request-'+$binding.id)}
        'binding-reference' {Assert-T10 (@($binding.steps).Count -eq 1 -and $binding.steps[0].type -ceq 'binding-reference') ('kind-binding-ref-'+$binding.id)}
        'evidence-reference' {Assert-T10 (@($binding.steps).Count -eq 1 -and $binding.steps[0].type -ceq 'evidence-reference') ('kind-evidence-ref-'+$binding.id)}
        'ui-sequence' {Assert-T10 (@($binding.steps|Where-Object{$_.type -cin @('binding-reference','evidence-reference')}).Count -eq 0) ('kind-ui-sequence-'+$binding.id)}
    }
    foreach($step in $binding.steps){
        switch([string]$step.type){
            'request' {
                Props-T10 $step @('type','id','actor','sessionSource','csrfSource','method','route','body','content','expected') ('request-props-'+$binding.id+'-'+$step.id)
                Assert-T10 ($step.actor -cin $allowedActors -and $step.sessionSource -cin $allowedActors) ('request-actor-'+$binding.id+'-'+$step.id)
                Assert-T10 ($step.method -cin @('GET','POST') -and [string]$step.route -cmatch $allowedRoutes -and [string]$step.route -cnotmatch '[?#*]|\.\.\.') ('request-route-'+$binding.id+'-'+$step.id)
                if($step.method -ceq 'GET'){Assert-T10 ($step.csrfSource -ceq 'none' -and $null -eq $step.body) ('get-contract-'+$binding.id+'-'+$step.id)}
                else{Assert-T10 ($step.csrfSource -ceq 'rendered' -and $step.body -cin $requestIds) ('post-contract-'+$binding.id+'-'+$step.id)}
                if($null -ne $step.content){$consumed.Add([string]$step.content)}
                if($step.body -ceq 'REQ-GRANT-REVOKE'){$revokeRequests++}
            }
            'ui-local' {
                Props-T10 $step @('type','id','actor','sessionSource','action','content','expected') ('ui-props-'+$binding.id+'-'+$step.id)
                Assert-T10 ($step.actor -cin $allowedActors -and $step.sessionSource -cin $allowedActors) ('ui-actor-'+$binding.id+'-'+$step.id)
                Assert-T10 ($step.action -cin @('open-editor','enter-tab-value','navigate','cancel-navigation','switch-actor')) ('ui-action-'+$binding.id+'-'+$step.id)
                if($null -ne $step.content){$consumed.Add([string]$step.content)}
            }
            'state-transition' {
                Props-T10 $step @('type','id','actor','transition','sourceContext','targetContext','expected') ('transition-props-'+$binding.id+'-'+$step.id)
                Assert-T10 ($step.actor -cin $allowedActors -and -not [string]::IsNullOrWhiteSpace([string]$step.sourceContext) -and -not [string]::IsNullOrWhiteSpace([string]$step.targetContext)) ('transition-context-'+$binding.id+'-'+$step.id)
                Assert-T10 ($step.transition -cin @('expire-idle','expire-absolute','advance-current-separate-session','apply-password-reset','apply-grant-revoke')) ('transition-kind-'+$binding.id+'-'+$step.id)
            }
            'observation' {Props-T10 $step @('type','id','actor','observer','expected') ('observation-props-'+$binding.id+'-'+$step.id);Assert-T10 ($step.actor -cin $allowedActors -and $step.observer -cin @($o.observers.id)) ('observation-context-'+$binding.id+'-'+$step.id)}
            'binding-reference' {Props-T10 $step @('type','id','bindingRef','expected') ('binding-ref-props-'+$binding.id);Assert-T10 ($binding.id -ceq 'UI-022-SAVE' -and $step.bindingRef -ceq 'UI-022-STAGE') 'binding-ref-exact'}
            'evidence-reference' {Props-T10 $step @('type','id','evidenceRef','expected') ('evidence-ref-props-'+$binding.id);Assert-T10 ($binding.id -ceq 'UI-015-OWNER-REVOKE' -and $step.evidenceRef -ceq 'REV-E1') 'evidence-ref-exact'}
            default {Assert-T10 $false ('unknown-step-'+$binding.id)}
        }
    }
}
Assert-T10 ($revokeRequests -eq 1) 'single-revoke-request'
Assert-T10 (@($b.bindings|Where-Object{$_.id -in @('HTTP-013-ACTIVE','HTTP-106-PROTECTED-SET')}|ForEach-Object{$_.steps}|Where-Object{$_.body -ceq 'REQ-EDITOR-SAVE'}).Count -eq 0) 'negative-no-save'
Assert-T10 (@($b.bindings|ForEach-Object{$_.steps}|Where-Object{$_.type -ceq 'request' -and [string]$_.route -match 'restore/stage'}).Count -eq 0) 'no-restore-stage'

$requiredMembers=@('P013-SAFE','P104-1M.exact','P104-1M.plusOne','P104-TEXT200K.exact','P104-TEXT200K.plusOne','P104-NODES20K.exact','P104-NODES20K.plusOne','P104-DEPTH32.exact','P104-DEPTH32.plusOne')
$requiredMembers+=@('event','script','iframe','css-url','css-position','template-expression','template-tag','template-comment'|ForEach-Object{'P104-ACTIVE-SET.'+$_})
$requiredMembers+=@('local','http','https'|ForEach-Object{'P106-SAFE-LINKS.'+$_})
$requiredMembers+=@('javascript','mixed-case','entity','encoded-control','data','file','vbscript','protocol-relative','userinfo','backslash'|ForEach-Object{'P106-UNSAFE-SET.'+$_})
foreach($member in $requiredMembers){Assert-T10 ($member -cin $consumed) ('member-consumed-'+$member)}
$row33=@($b.bindings|Where-Object{$_.id -ceq 'UI-104-NORMALISE'})[0]
Exact-T10 $row33.steps.content @('P013-SAFE','P104-1M.exact','P104-1M.plusOne','P104-TEXT200K.exact','P104-TEXT200K.plusOne','P104-NODES20K.exact','P104-NODES20K.plusOne','P104-DEPTH32.exact','P104-DEPTH32.plusOne') 'row33-members'
Exact-T10 $row33.steps.type @('request','request','request','request','request','request','request','request','request') 'row33-step-types'
Exact-T10 $row33.steps.id @('check-P013-SAFE','check-P104-1M-exact','check-P104-1M-plusOne','check-P104-TEXT200K-exact','check-P104-TEXT200K-plusOne','check-P104-NODES20K-exact','check-P104-NODES20K-plusOne','check-P104-DEPTH32-exact','check-P104-DEPTH32-plusOne') 'row33-step-ids'
Exact-T10 $row33.steps.expected @('accepted-normalised-no-mutation','accepted-normalised-no-mutation','refused-no-mutation','accepted-normalised-no-mutation','refused-no-mutation','accepted-normalised-no-mutation','refused-no-mutation','accepted-normalised-no-mutation','refused-no-mutation') 'row33-expectations'
foreach($step in $row33.steps){Assert-T10 ((RequestSignature-T10 $step) -ceq ('S-EDIT|S-EDIT|rendered|POST|/manage/pages/{page}/edit/check/|REQ-EDITOR-CHECK|'+$step.content)) ('row33-request-signature-'+$step.id)}
Assert-T10 (@($row33.steps|Where-Object{[string]$_.content -like '*.plusOne' -and $_.body -ceq 'REQ-EDITOR-SAVE'}).Count -eq 0) 'row33-plus-no-save'

PinSequence-T10 'UI-013-POSITIVE' @('request','request') @('check','save') @('accepted-normalised','one-revision')
PinRequests-T10 'UI-013-POSITIVE' @('S-EDIT|S-EDIT|rendered|POST|/manage/pages/{page}/edit/check/|REQ-EDITOR-CHECK|P013-SAFE','S-EDIT|S-EDIT|rendered|POST|/manage/pages/{page}/edit/save/|REQ-EDITOR-SAVE|runtime.normalisedChanges')
PinSequence-T10 'UI-015-UNSAVED' @('request','ui-local') @('open','enter-canary') @('editor-open','tab-memory-only')
PinRequests-T10 'UI-015-UNSAVED' @('S-EDIT|S-EDIT|none|GET|/manage/pages/{page}/edit/|<null>|<null>')
$unsaved=@($b.bindings|Where-Object{$_.id -ceq 'UI-015-UNSAVED'})[0];Exact-T10 @($unsaved.steps|Where-Object{$_.type -ceq 'ui-local'}|ForEach-Object{$_.action}) @('enter-tab-value') 'pin-local-UI-015-UNSAVED'
Exact-T10 @($unsaved.steps|Where-Object{$_.type -cne 'request'}|ForEach-Object{NonRequestSignature-T10 $_}) @('S-EDIT|S-EDIT|enter-tab-value|private.TEST10-SYNTHETIC-CANARY|<null>|<null>|<null>|<null>') 'pin-context-UI-015-UNSAVED'
PinSequence-T10 'UI-015-EXPLICIT-SAVE' @('request','request') @('check','save') @('accepted-normalised','one-revision-after-explicit-save')
PinRequests-T10 'UI-015-EXPLICIT-SAVE' @('S-EDIT|S-EDIT|rendered|POST|/manage/pages/{page}/edit/check/|REQ-EDITOR-CHECK|private.TEST10-SYNTHETIC-CANARY','S-EDIT|S-EDIT|rendered|POST|/manage/pages/{page}/edit/save/|REQ-EDITOR-SAVE|runtime.normalisedChanges')
PinSequence-T10 'UI-022-CANCEL' @('ui-local','ui-local','ui-local') @('navigate-away','navigate-back','cancel-navigation') @('no-mutation','comparison-visible-no-mutation','no-mutation')
$cancel=@($b.bindings|Where-Object{$_.id -ceq 'UI-022-CANCEL'})[0];Exact-T10 $cancel.steps.action @('navigate','navigate','cancel-navigation') 'pin-local-UI-022-CANCEL'
Exact-T10 @($cancel.steps|ForEach-Object{NonRequestSignature-T10 $_}) @('S-EDIT|S-EDIT|navigate|away-from-comparison|<null>|<null>|<null>|<null>','S-EDIT|S-EDIT|navigate|historical-comparison|<null>|<null>|<null>|<null>','S-EDIT|S-EDIT|cancel-navigation|historical-comparison|<null>|<null>|<null>|<null>') 'pin-context-UI-022-CANCEL'
PinSequence-T10 'UI-022-STAGE' @('request','request') @('prepare','apply') @('prepared-read-only','one-role-limited-revision')
PinRequests-T10 'UI-022-STAGE' @('S-EDIT|S-EDIT|rendered|POST|/manage/pages/{page}/versions/{version}/restore/prepare/|REQ-RESTORE-PREPARE|<null>','S-EDIT|S-EDIT|rendered|POST|/manage/pages/{page}/versions/{version}/restore/apply/|REQ-RESTORE-APPLY|<null>')
PinSequence-T10 'UI-022-OWNER-CONTROL' @('request','request','request') @('compare','prepare','apply') @('comparison-visible-no-mutation','prepared-read-only','one-full-compatible-revision')
PinRequests-T10 'UI-022-OWNER-CONTROL' @('OWNER|OWNER|none|GET|/manage/pages/{page}/versions/{version}/compare/|<null>|<null>','OWNER|OWNER|rendered|POST|/manage/pages/{page}/versions/{version}/restore/prepare/|REQ-RESTORE-PREPARE|<null>','OWNER|OWNER|rendered|POST|/manage/pages/{page}/versions/{version}/restore/apply/|REQ-RESTORE-APPLY|<null>')
PinSequence-T10 'UI-023-COMPATIBLE-CONTROL' @('request','request') @('prepare','apply') @('prepared-read-only','one-role-limited-revision')
PinRequests-T10 'UI-023-COMPATIBLE-CONTROL' @('S-EDIT|S-EDIT|rendered|POST|/manage/pages/{page}/versions/{version}/restore/prepare/|REQ-RESTORE-PREPARE|<null>','S-EDIT|S-EDIT|rendered|POST|/manage/pages/{page}/versions/{version}/restore/apply/|REQ-RESTORE-APPLY|<null>')
PinSequence-T10 'UI-104-POSITIVE' @('request','request') @('check','save') @('accepted-normalised','one-revision')
PinRequests-T10 'UI-104-POSITIVE' @('S-EDIT|S-EDIT|rendered|POST|/manage/pages/{page}/edit/check/|REQ-EDITOR-CHECK|P013-SAFE','S-EDIT|S-EDIT|rendered|POST|/manage/pages/{page}/edit/save/|REQ-EDITOR-SAVE|runtime.normalisedChanges')
PinSequence-T10 'UI-106-POSITIVE' @('request','request') @('check','save') @('accepted-normalised','one-revision')
PinRequests-T10 'UI-106-POSITIVE' @('S-EDIT|S-EDIT|rendered|POST|/manage/pages/{page}/edit/check/|REQ-EDITOR-CHECK|P106-SAFE-LINKS.local','S-EDIT|S-EDIT|rendered|POST|/manage/pages/{page}/edit/save/|REQ-EDITOR-SAVE|runtime.normalisedChanges')
PinSequence-T10 'UI-118-EXPIRY' @('request','ui-local','state-transition','request') @('open','enter-canary','expire-session','check-after-expiry') @('editor-open','tab-memory-only','session-expired','session-denied-no-mutation')
PinRequests-T10 'UI-118-EXPIRY' @('S-EDIT|S-EDIT|none|GET|/manage/pages/{page}/edit/|<null>|<null>','S-EDIT-EXPIRED|S-EDIT-EXPIRED|rendered|POST|/manage/pages/{page}/edit/check/|REQ-EDITOR-CHECK|private.TEST10-SYNTHETIC-CANARY')
$expiry=@($b.bindings|Where-Object{$_.id -ceq 'UI-118-EXPIRY'})[0];Exact-T10 @($expiry.steps|Where-Object{$_.type -ceq 'ui-local'}).action @('enter-tab-value') 'pin-local-UI-118-EXPIRY';Exact-T10 @($expiry.steps|Where-Object{$_.type -ceq 'state-transition'}).transition @('expire-idle') 'pin-transition-UI-118-EXPIRY'
Exact-T10 @($expiry.steps|Where-Object{$_.type -cne 'request'}|ForEach-Object{NonRequestSignature-T10 $_}) @('S-EDIT|S-EDIT|enter-tab-value|private.TEST10-SYNTHETIC-CANARY|<null>|<null>|<null>|<null>','S-EDIT|<null>|<null>|<null>|expire-idle|S-EDIT|S-EDIT-EXPIRED|<null>') 'pin-context-UI-118-EXPIRY'
PinSequence-T10 'UI-118-CONFLICT' @('request','state-transition','request') @('check','advance-current','stale-save') @('accepted-normalised','one-reviewed-branch-revision','conflict-no-partial-mutation')
PinRequests-T10 'UI-118-CONFLICT' @('S-EDIT|S-EDIT|rendered|POST|/manage/pages/{page}/edit/check/|REQ-EDITOR-CHECK|private.TEST10-SYNTHETIC-CANARY','S-EDIT|S-EDIT|rendered|POST|/manage/pages/{page}/edit/save/|REQ-EDITOR-SAVE|runtime.normalisedChanges')
$conflict=@($b.bindings|Where-Object{$_.id -ceq 'UI-118-CONFLICT'})[0];Exact-T10 @($conflict.steps|Where-Object{$_.type -ceq 'state-transition'}).transition @('advance-current-separate-session') 'pin-transition-UI-118-CONFLICT'
Exact-T10 @($conflict.steps|Where-Object{$_.type -eq 'state-transition'}|ForEach-Object{NonRequestSignature-T10 $_}) @('S-EDIT|<null>|<null>|<null>|advance-current-separate-session|current-at-check|current-advanced|<null>') 'pin-context-UI-118-CONFLICT'

foreach($payload in @($p.payloads|Where-Object{$_.kind -ceq 'boundary-pair'})){
    if($payload.generator -ceq 'repeat'){$exact=[string]$payload.unit*[int]$payload.exactCount;$plus=[string]$payload.unit*[int]$payload.plusOneCount}
    else{$exact=([string]$payload.open*[int]$payload.exactCount)+[string]$payload.text+([string]$payload.close*[int]$payload.exactCount);$plus=([string]$payload.open*[int]$payload.plusOneCount)+[string]$payload.text+([string]$payload.close*[int]$payload.plusOneCount)}
    Assert-T10 ((Sha-T10 $exact) -ceq $payload.exactSha256) ('boundary-exact-'+$payload.id);Assert-T10 ((Sha-T10 $plus) -ceq $payload.plusOneSha256) ('boundary-plus-'+$payload.id)
}
foreach($payload in @($p.payloads|Where-Object{$_.kind -cin @('literal-html','request-template')})){Assert-T10 ((Sha-T10 ([string]$payload.value)) -ceq $payload.sha256) ('payload-hash-'+$payload.id)}
foreach($payload in @($p.payloads|Where-Object{$_.kind -cin @('literal-html-set','literal-url-set')})){foreach($v in $payload.values){Assert-T10 ((Sha-T10 ([string]$v.value)) -ceq $v.sha256) ('member-hash-'+$payload.id+'-'+$v.id)}}
foreach($payload in @($p.payloads|Where-Object{$_.id -in @('P106-SAFE-LINKS','P106-UNSAFE-SET')})){foreach($v in $payload.values){$e=([string]$v.value).Replace('&','&amp;').Replace('"','&quot;').Replace('<','&lt;').Replace('>','&gt;');$projection='{"main_text":'+(JsonString-T10 ('<p><a href="'+$e+'">EDITOR-LINK-CANARY</a></p>'))+'}';Assert-T10 ((Sha-T10 $projection) -ceq $v.projectedSha256) ('projection-hash-'+$payload.id+'-'+$v.id)}}
Exact-T10 $p.privateReferences.label @('OLD-SYNTHETIC-SECRET','NEW-SYNTHETIC-SECRET','TEST10-SYNTHETIC-CANARY') 'private-labels'
Assert-T10 (@($p.contentProjections).Count -eq 4) 'projection-count'
foreach($placeholder in $p.placeholderBindings){Props-T10 $placeholder @('token','source','type') ('placeholder-props-'+$placeholder.token)}
Exact-T10 $p.placeholderBindings.token @('{identifiers.page}','{identifiers.currentRevision}','{identifiers.historicalRevision}','{identifiers.incompatibleRevision}','{identifiers.editUser}','{identifiers.ownerUser}','{private.OLD-SYNTHETIC-SECRET}','{private.NEW-SYNTHETIC-SECRET}','{private.TEST10-SYNTHETIC-CANARY}','{runtime.generation}','{runtime.currentRevision}','{runtime.operationId}','{runtime.checkReceipt}','{runtime.preparation}','{runtime.normalisedChanges}','{content.projectedChanges}') 'placeholder-tokens'
Exact-T10 $p.placeholderBindings.source @('summary.identifiers.page','summary.identifiers.currentRevision','summary.identifiers.historicalRevision','summary.identifiers.incompatibleRevision','summary.identifiers.editUser','summary.identifiers.ownerUser','private.passwords.S-EDIT','run-private.generatedNextPassword.S-EDIT','private.canary','runtime.authGeneration','runtime.currentRevision','runtime.operationId','runtime.checkReceipt','runtime.preparation','runtime.normalisedChanges','binding.contentProjection') 'placeholder-sources'
Exact-T10 $p.placeholderBindings.type @('uuid','uuid','uuid','uuid','positive-int','positive-int','private-string','private-string','private-string','positive-int','uuid','uuid','signed-string','signed-string','canonical-json','canonical-json') 'placeholder-types'
foreach($private in $p.privateReferences){Props-T10 $private @('label','source') ('private-props-'+$private.label)}
Exact-T10 $p.privateReferences.source @('private.passwords.S-EDIT','run-private.generatedNextPassword.S-EDIT','private.canary') 'private-sources'
$requests=@($p.payloads|Where-Object{$_.kind -ceq 'request-template'})
foreach($request in $requests){Props-T10 $request @('id','kind','contentType','value','sha256') ('request-template-props-'+$request.id)}
Exact-T10 $requests.contentType @('application/x-www-form-urlencoded','application/x-www-form-urlencoded','application/x-www-form-urlencoded','application/x-www-form-urlencoded','application/json','application/json','application/x-www-form-urlencoded','application/x-www-form-urlencoded') 'request-content-types'
Exact-T10 $requests.value @('password={private.NEW-SYNTHETIC-SECRET}','username=test10-s-edit&password={private.OLD-SYNTHETIC-SECRET}','username=test10-s-edit&password={private.NEW-SYNTHETIC-SECRET}','page={identifiers.page}&action=revoke','{"baseRevisionId":"{runtime.currentRevision}","changes":{content.projectedChanges},"draftBasis":null,"editingFrom":"current","generation":{runtime.generation},"protocol":"page-editor-v1","stageId":null}','{"baseRevisionId":"{runtime.currentRevision}","changes":{runtime.normalisedChanges},"checkReceipt":"{runtime.checkReceipt}","draftBasis":null,"editingFrom":"current","generation":{runtime.generation},"operationId":"{runtime.operationId}","protocol":"page-editor-v1","stageId":null}','generation={runtime.generation}','generation={runtime.generation}&operation_id={runtime.operationId}&preparation={runtime.preparation}&confirm_input_replacement=yes') 'request-template-values'
$knownTokens=@($p.placeholderBindings.token);foreach($request in $requests){foreach($match in [regex]::Matches([string]$request.value,'\{[A-Za-z0-9._-]+\}')){Assert-T10 ($match.Value -cin $knownTokens) ('known-placeholder-'+$request.id+'-'+$match.Value)}}
$htmlProjection=@($p.contentProjections|Where-Object{$_.id -ceq 'html-main-text'})[0];Props-T10 $htmlProjection @('id','appliesTo','field','wrapper','private') 'projection-props-html';Exact-T10 $htmlProjection.appliesTo @('P013-SAFE','P104-1M.*','P104-TEXT200K.*','P104-NODES20K.*','P104-DEPTH32.*','P104-ACTIVE-SET.*') 'projection-applies-html';Assert-T10 ($htmlProjection.field -ceq 'main_text' -and $htmlProjection.wrapper -ceq 'canonical-json-string' -and $htmlProjection.private -eq $false) 'projection-contract-html'
$linkProjection=@($p.contentProjections|Where-Object{$_.id -ceq 'link-main-text'})[0];Props-T10 $linkProjection @('id','appliesTo','field','wrapper','escapeOrder','private') 'projection-props-link';Exact-T10 $linkProjection.appliesTo @('P106-SAFE-LINKS.*','P106-UNSAFE-SET.*') 'projection-applies-link';Exact-T10 $linkProjection.escapeOrder @('&=>&amp;','"=>&quot;','<=>&lt;','>=>&gt;') 'projection-escape-link';Assert-T10 ($linkProjection.field -ceq 'main_text' -and $linkProjection.wrapper -ceq '<p><a href="{attributeEscaped}">EDITOR-LINK-CANARY</a></p>' -and $linkProjection.private -eq $false) 'projection-contract-link'
$canaryProjection=@($p.contentProjections|Where-Object{$_.id -ceq 'canary-main-text'})[0];Props-T10 $canaryProjection @('id','appliesTo','field','wrapper','private') 'projection-props-canary';Exact-T10 $canaryProjection.appliesTo @('private.TEST10-SYNTHETIC-CANARY') 'projection-applies-canary';Assert-T10 ($canaryProjection.field -ceq 'main_text' -and $canaryProjection.wrapper -ceq 'canonical-json-string' -and $canaryProjection.private -eq $true) 'projection-contract-canary'
$invalidProjection=@($p.contentProjections|Where-Object{$_.id -ceq 'canary-invalid-owner-field'})[0];Props-T10 $invalidProjection @('id','appliesTo','field','wrapper','private') 'projection-props-invalid';Exact-T10 $invalidProjection.appliesTo @('private.TEST10-SYNTHETIC-CANARY.invalid-owner-field') 'projection-applies-invalid';Assert-T10 ($invalidProjection.field -ceq 'h1' -and $invalidProjection.wrapper -ceq 'canonical-json-string' -and $invalidProjection.private -eq $true) 'projection-contract-invalid'

$observerIds=@($o.observers.id)
Exact-T10 $observerIds @('OBS-014-SECRET-SINKS','OBS-021-CACHE','OBS-022-PROTECTED-UNCHANGED','OBS-106-CLIENT-NETWORK','OBS-106-SERVER-EGRESS','OBS-118-BROWSER-STORAGE','OBS-REV-E1') 'observer-ids'
Assert-T10 (@($o.observers|Where-Object{$_.implementationStatus -cne 'unbound'}).Count -eq 0) 'observers-unbound'
$obs22=@($o.observers|Where-Object{$_.id -ceq 'OBS-022-PROTECTED-UNCHANGED'})[0]
Exact-T10 $obs22.inputBindings @('UI-022-STAGE','UI-022-OWNER-CONTROL') 'obs22-inputs'
Exact-T10 $obs22.output @('status','complete','commonUnchangedByField','employeeOwnerFieldsUnchangedByField','ownerSnapshotFieldsRestoredByField') 'obs22-output'
Exact-T10 $obs22.commonFields @('url','parent','page-position','publication','grants','stable','shared-header-footer') 'obs22-common'
Props-T10 $obs22 @('id','implementationStatus','source','inputBindings','sinkSet','output','commonFields','employeeOwnerFields','ownerSnapshotFields','semantics') 'obs22-props'
Assert-T10 ($null -eq $obs22.source) 'obs22-source-unbound'
Exact-T10 $obs22.sinkSet @('url','parent','page-position','publication','grants','stable','shared-header-footer','employee-owner-fields','owner-snapshot-fields') 'obs22-sinks'
Exact-T10 $obs22.employeeOwnerFields @('h1','seo','block-layout','protected-media') 'obs22-employee-fields'
Exact-T10 $obs22.ownerSnapshotFields @('h1','seo','block-layout','protected-media') 'obs22-owner-fields'
Assert-T10 ($obs22.semantics -ceq 'missing-branch-or-field=BLOCKED; complete-false=FAIL; complete-and-all-branch-booleans-true=PASS') 'obs22-semantics'
$rev=@($o.observers|Where-Object{$_.id -ceq 'OBS-REV-E1'})[0]
Assert-T10 ($null -eq $rev.source -and $rev.eventTuple.level -ceq 'INFO' -and $rev.eventTuple.result -ceq 'SUCCESS' -and $rev.eventTuple.actorId -ceq '{identifiers.ownerUser}' -and $rev.eventTuple.objectRef -ceq 'id:{identifiers.editUser}') 'rev-event-tuple'
Props-T10 $rev @('id','implementationStatus','source','candidateSources','inputBindings','sinkSet','output','eventTuple','semantics') 'rev-props'
Exact-T10 $rev.candidateSources @('accounts.models.PageGrant','accounts.models.UserProfile','audit.models.AuditEvent') 'rev-candidate-sources'
Exact-T10 $rev.inputBindings @('UI-023-OWNER-REVOKE') 'rev-inputs'
Exact-T10 $rev.sinkSet @('page-grant','employee-generation','cursor-bounded-audit-event') 'rev-sinks'
Exact-T10 $rev.output @('status','grantCountBefore','grantCountAfter','generationBefore','generationAfter','matchingAuditEvents','complete') 'rev-output'
Props-T10 $rev.eventTuple @('category','level','code','source','result','actorId','objectKind','objectRef','occurrenceCount','countIsLowerBound') 'rev-event-props'
Assert-T10 ($rev.eventTuple.category -ceq 'access' -and $rev.eventTuple.code -ceq 'AUTH_GRANT_REVOKED' -and $rev.eventTuple.source -ceq 'application' -and $rev.eventTuple.objectKind -ceq 'user' -and $rev.eventTuple.occurrenceCount -eq 1 -and $rev.eventTuple.countIsLowerBound -eq $false) 'rev-event-contract'
Assert-T10 ($rev.semantics -ceq 'missing-authority-or-drift-or-concurrency=BLOCKED; complete-wrong-mutation=FAIL; grant-1-to-0-and-generation-plus-1-and-exact-one-event=PASS') 'rev-semantics'

if($failures.Count){throw ('TEST10_REGISTRY_STATIC_FAILED: '+($failures -join ','))}
[ordered]@{schema='test10a-registry-static-v2';status='PASS';assertions=$assertions;registryReady=$false;unboundBindings=40;unboundObservers=7;bindingsSha256=(Get-FileHash -LiteralPath $bindingsPath -Algorithm SHA256).Hash.ToLowerInvariant();payloadRegistrySha256=(Get-FileHash -LiteralPath $payloadsPath -Algorithm SHA256).Hash.ToLowerInvariant();observerRegistrySha256=(Get-FileHash -LiteralPath $observersPath -Algorithm SHA256).Hash.ToLowerInvariant();dockerCalled=$false}|ConvertTo-Json -Compress
