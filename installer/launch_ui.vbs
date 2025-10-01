' Launch Streamlit UI without showing PowerShell window
Dim shell
Set shell = CreateObject("WScript.Shell")
' Resolve project root relative to this script when installed into {app}
appPath = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
' run-ui.ps1 is in scripts\run-ui.ps1 relative to app root
cmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File """ & appPath & "\scripts\run-ui.ps1"""" 
' 0 = window style hidden, True = wait? we use False to not block
shell.Run cmd, 0, False
