' Launch Dou SnapTrack UI without showing a console (local dev)
Dim shell
Set shell = CreateObject("WScript.Shell")
' Project root is the folder containing this VBS
appPath = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
' Run the managed launcher (handles venv/bootstrap and lifecycle)
cmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & appPath & "\scripts\run-ui-managed.ps1"""" 
' 0 = hidden, False = do not wait
shell.Run cmd, 0, False
