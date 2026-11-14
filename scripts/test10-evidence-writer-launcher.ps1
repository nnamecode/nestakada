$ErrorActionPreference='Stop';Set-StrictMode -Version Latest
$blocked='{"schema":"test10a-writer-launch-v1","status":"BLOCKED"}'
$passed='{"schema":"test10a-writer-launch-v1","status":"PASS"}'
function Finish([string]$Value,[int]$Code){[Console]::Out.WriteLine($Value);exit $Code}
function Quote-Argument([string]$Value){
 if($null-eq$Value-or$Value.Contains('"')){throw'T10_LAUNCH_ARGUMENT'}
 $slashes=0;for($index=$Value.Length-1;$index-ge0-and$Value[$index]-eq'\';$index--){$slashes++}
 return '"'+$Value+(''+'\'*$slashes)+'"'
}
function Assert-Ordinary([string]$Anchor,[string]$Target,[bool]$Directory){
 $root=[IO.Path]::GetFullPath($Anchor).TrimEnd([IO.Path]::DirectorySeparatorChar);$current=[IO.Path]::GetFullPath($Target);$leaf=$true
 if(!$current.StartsWith($root+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)-and![String]::Equals($current.TrimEnd([IO.Path]::DirectorySeparatorChar),$root,[StringComparison]::OrdinalIgnoreCase)){throw'T10_LAUNCH_PATH'}
 while($true){$attributes=[IO.File]::GetAttributes($current);if($attributes-band[IO.FileAttributes]::ReparsePoint){throw'T10_LAUNCH_REPARSE'};$actual=[bool]($attributes-band[IO.FileAttributes]::Directory);if(($leaf-and$actual-ne$Directory)-or(!$leaf-and!$actual)){throw'T10_LAUNCH_TYPE'};if([String]::Equals($current.TrimEnd([IO.Path]::DirectorySeparatorChar),$root,[StringComparison]::OrdinalIgnoreCase)){break};$current=[IO.Path]::GetDirectoryName($current);$leaf=$false}
}
function Wait-Child([Diagnostics.Process]$Process,[int]$TimeoutMs,[int]$Cap,[int]$KillWaitMs){
 $stdout=New-Object byte[] 512;$stderr=New-Object byte[] 512;$stdoutTask=$Process.StandardOutput.BaseStream.ReadAsync($stdout,0,512);$stderrTask=$Process.StandardError.BaseStream.ReadAsync($stderr,0,512)
 $stdoutTotal=0;$stderrTotal=0;$stdoutEof=$false;$stderrEof=$false;$overflow=$false;$watch=[Diagnostics.Stopwatch]::StartNew()
 while(!$overflow-and$watch.ElapsedMilliseconds-lt$TimeoutMs-and!($Process.HasExited-and$stdoutEof-and$stderrEof)){
  if(!$stdoutEof-and$stdoutTask.IsCompleted){$count=$stdoutTask.Result;if($count-eq0){$stdoutEof=$true}else{$stdoutTotal+=$count;if($stdoutTotal-gt$Cap){$overflow=$true}else{$stdoutTask=$Process.StandardOutput.BaseStream.ReadAsync($stdout,0,512)}}}
  if(!$stderrEof-and$stderrTask.IsCompleted){$count=$stderrTask.Result;if($count-eq0){$stderrEof=$true}else{$stderrTotal+=$count;if($stderrTotal-gt$Cap){$overflow=$true}else{$stderrTask=$Process.StandardError.BaseStream.ReadAsync($stderr,0,512)}}}
  if(!$overflow-and!($Process.HasExited-and$stdoutEof-and$stderrEof)){[Threading.Thread]::Sleep(10)}
 }
 $complete=$Process.HasExited-and$stdoutEof-and$stderrEof-and!$overflow
 if(!$complete){if(!$Process.HasExited){$Process.Kill()};if(!$Process.WaitForExit($KillWaitMs)){return $false};return $false};return $true
}
function Invoke-Launcher([object[]]$RawArgs){
 $child=$null
 try{
 if($RawArgs.Count-ne2-or$RawArgs[0]-cne'WriteManifest'-or$RawArgs[1]-cnotmatch'^[a-f0-9]{32}$'){Finish $blocked 2}
 $binary=[IO.Path]::Combine($PSHOME,'powershell.exe');$scripts=[IO.Path]::GetFullPath($PSScriptRoot);$repo=[IO.Path]::GetFullPath([IO.Path]::Combine($scripts,'..'));$writer=[IO.Path]::Combine($scripts,'test10-evidence-writer.ps1')
 Assert-Ordinary $PSHOME $binary $false;Assert-Ordinary $repo $scripts $true;Assert-Ordinary $repo $writer $false;Assert-Ordinary $repo $PSCommandPath $false
 $vector=@('-NoLogo','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',$writer,'-Mode','WriteManifest','-RunId',$RawArgs[1]);$quoted=@();foreach($value in $vector){$quoted+=Quote-Argument $value}
 $start=[Diagnostics.ProcessStartInfo]::new();$start.FileName=$binary;$start.Arguments=$quoted-join' ';$start.UseShellExecute=$false;$start.CreateNoWindow=$true;$start.RedirectStandardOutput=$true;$start.RedirectStandardError=$true;$start.RedirectStandardInput=$false
 $child=[Diagnostics.Process]::new();$child.StartInfo=$start;if(!$child.Start()){Finish $blocked 2}
 if(!(Wait-Child $child 30000 4096 5000)){Finish $blocked 2}
 if($child.ExitCode-ne0){Finish $blocked 2};Finish $passed 0
}catch{
 try{if($null-ne$child-and!$child.HasExited){$child.Kill();$null=$child.WaitForExit(5000)}}catch{}
 Finish $blocked 2
 }}
if($MyInvocation.InvocationName-cne'.'){Invoke-Launcher @($args)}
