' Launch SnapTrack UI from repo root, independent of installer
Dim shell, fso, repoRoot, cmd
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
' repo root is the parent folder of this VBS (C:\Projetos)
repoRoot = fso.GetParentFolderName(WScript.ScriptFullName)
' Call the managed launcher in scripts/ from the repo
cmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File " _
	& Chr(34) & repoRoot & "\scripts\run-ui-managed.ps1" & Chr(34) & " -Port 8501"
' 0 = hidden, False = do not wait
shell.Run cmd, 0, False
