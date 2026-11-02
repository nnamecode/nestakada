[CmdletBinding()]
param([ValidateSet('Prepare','Start','Stop','Status','Tests','Transport','Calibrate','ArchiveUnit')][string]$Action='Status', [switch]$Bootstrap)
$ErrorActionPreference='Stop'
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
if($Action -eq 'Prepare'){
    $private=Join-Path $repo 'work/dev15-20261102/private'
    if(!(Test-Path -LiteralPath $private)){New-Item -ItemType Directory -Path $private -Force|Out-Null}
    $item=Get-Item -LiteralPath $private -Force
    if($item.Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'TRUST_PRIVATE_LINK'}
    $identity=[Security.Principal.WindowsIdentity]::GetCurrent()
    $acl=[IO.Directory]::GetAccessControl($private,[Security.AccessControl.AccessControlSections]::Access)
    $acl.SetAccessRuleProtection($true,$false)
    foreach($rule in @($acl.Access)){$acl.RemoveAccessRuleSpecific($rule)}
    foreach($sid in @($identity.User,(New-Object Security.Principal.SecurityIdentifier('S-1-5-18')))){
        $rule=New-Object Security.AccessControl.FileSystemAccessRule($sid,'FullControl','ContainerInherit,ObjectInherit','None','Allow')
        $acl.AddAccessRule($rule)
    }
    [IO.Directory]::SetAccessControl($private,$acl)
}
$arguments=@((Join-Path $repo 'tools/local_trust.mjs'),$Action)
if($Bootstrap){$arguments+='--bootstrap'}
& node @arguments
if($LASTEXITCODE -ne 0){throw 'TRUST_ACTION_FAILED; inspect the scoped redacted evidence.'}
