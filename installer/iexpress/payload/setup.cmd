@echo off
setlocal
REM Extracted next to this file: project.zip, install.ps1, run-ui-managed.ps1, launch_ui_managed.vbs
set APPDIR=%LocalAppData%\dou_snaptrack
if not exist "%APPDIR%" mkdir "%APPDIR%"
if not exist "%APPDIR%\scripts" mkdir "%APPDIR%\scripts"
if not exist "%APPDIR%\logs" mkdir "%APPDIR%\logs"
REM Unpack project.zip into %APPDIR%
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -Force '%~dp0project.zip' '%APPDIR%'"
REM Copy helper scripts (managed launcher)
copy /Y "%~dp0install.ps1" "%APPDIR%\scripts\install.ps1" >NUL
copy /Y "%~dp0run-ui-managed.ps1" "%APPDIR%\scripts\run-ui-managed.ps1" >NUL
copy /Y "%~dp0launch_ui_managed.vbs" "%APPDIR%\launch_ui_managed.vbs" >NUL
REM Run install silently and log
powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%APPDIR%\scripts\install.ps1" > "%APPDIR%\logs\installer.log" 2>&1
REM Create Start Menu and Desktop shortcuts to managed launcher
powershell -NoProfile -ExecutionPolicy Bypass -Command "$w=New-Object -ComObject WScript.Shell; $lnk1=$w.CreateShortcut([IO.Path]::Combine($env:APPDATA,'Microsoft\\Windows\\Start Menu\\Programs','Dou SnapTrack.lnk')); $lnk1.TargetPath=[IO.Path]::Combine($env:LocalAppData,'dou_snaptrack','launch_ui_managed.vbs'); $lnk1.WorkingDirectory=[IO.Path]::Combine($env:LocalAppData,'dou_snaptrack'); $lnk1.Save(); $desktop=[Environment]::GetFolderPath('Desktop'); $lnk2=$w.CreateShortcut([IO.Path]::Combine($desktop,'Dou SnapTrack.lnk')); $lnk2.TargetPath=[IO.Path]::Combine($env:LocalAppData,'dou_snaptrack','launch_ui_managed.vbs'); $lnk2.WorkingDirectory=[IO.Path]::Combine($env:LocalAppData,'dou_snaptrack'); $lnk2.Save()"
endlocal
