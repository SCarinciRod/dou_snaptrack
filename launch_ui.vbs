' Launch Dou SnapTrack UI without showing a console (local dev)
Dim shell, fso, appPath, cmd
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
' Project root is the folder containing this VBS
appPath = fso.GetParentFolderName(WScript.ScriptFullName)
' Run the managed launcher (handles venv/bootstrap and lifecycle)
cmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File " _
	& Chr(34) & appPath & "\scripts\run-ui-managed.ps1" & Chr(34)
' 0 = hidden, False = do not wait
shell.Run cmd, 0, False
