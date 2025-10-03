$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) '..')).Path
$vbs = Join-Path $root 'launch_ui.vbs'
if (-not (Test-Path $vbs)) { Write-Error "Launcher VBS não encontrado em $vbs" }

$desktop = [Environment]::GetFolderPath('Desktop')
$lnkPath = Join-Path $desktop 'Dou SnapTrack.lnk'
$WshShell = New-Object -ComObject WScript.Shell
$shortcut = $WshShell.CreateShortcut($lnkPath)
$shortcut.TargetPath = $vbs
$shortcut.WorkingDirectory = $root
$shortcut.IconLocation = 'shell32.dll,220'
$shortcut.Save()

Write-Host "Atalho criado: $lnkPath"
