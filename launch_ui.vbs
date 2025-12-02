' Launch SnapTrack UI with splash screen (fast startup)
' This launcher shows an animated splash immediately while Streamlit loads in background
Dim shell, fso, repoRoot, cmd
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
' repo root is the parent folder of this VBS (C:\Projetos)
repoRoot = fso.GetParentFolderName(WScript.ScriptFullName)
' Call the splash launcher directly for fastest startup
cmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File " _
	& Chr(34) & repoRoot & "\scripts\run-ui-splash.ps1" & Chr(34)
' 0 = hidden, False = do not wait
shell.Run cmd, 0, False
