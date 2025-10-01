' Launch managed UI (ties lifecycle to browser window) without console
Dim shell
Set shell = CreateObject("WScript.Shell")
appPath = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
cmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File """ & appPath & "\scripts\run-ui-managed.ps1"""" 
shell.Run cmd, 0, False
