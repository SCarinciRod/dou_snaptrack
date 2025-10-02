' Launch managed UI (ties lifecycle to browser window) without console
Dim shell, fso, appPath, cmd
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
appPath = fso.GetParentFolderName(WScript.ScriptFullName)
cmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File " _
	& Chr(34) & appPath & "\scripts\run-ui-managed.ps1" & Chr(34)
shell.Run cmd, 0, False
