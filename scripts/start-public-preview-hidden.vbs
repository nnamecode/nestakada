Option Explicit

Dim fileSystem, shell, scriptDirectory, projectRoot, pythonPath, port, command, exitCode

Set fileSystem = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

scriptDirectory = fileSystem.GetParentFolderName(WScript.ScriptFullName)
projectRoot = fileSystem.GetParentFolderName(scriptDirectory)
pythonPath = shell.ExpandEnvironmentStrings("%USERPROFILE%") & "\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
port = "8765"

If WScript.Arguments.Count > 0 Then
    port = WScript.Arguments(0)
End If

If Not fileSystem.FileExists(pythonPath) Then
    WScript.Quit 2
End If

command = Chr(34) & pythonPath & Chr(34) & " -m http.server " & port & " --bind 127.0.0.1 --directory " & Chr(34) & projectRoot & Chr(34)
exitCode = shell.Run(command, 0, True)
WScript.Quit exitCode
