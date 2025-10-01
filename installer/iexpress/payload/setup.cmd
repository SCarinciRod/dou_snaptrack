@echo off
setlocal
REM Extracted next to this file: project.zip, install.ps1, run-ui.ps1, launch_ui.vbs
set APPDIR=%LocalAppData%\dou_snaptrack
if not exist "%APPDIR%" mkdir "%APPDIR%"
REM Unpack project.zip into %APPDIR%
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -Force '%~dp0project.zip' '%APPDIR%'"
REM Copy helper scripts
copy /Y "%~dp0install.ps1" "%APPDIR%\scripts\install.ps1" >NUL
copy /Y "%~dp0run-ui.ps1" "%APPDIR%\scripts\run-ui.ps1" >NUL
copy /Y "%~dp0launch_ui.vbs" "%APPDIR%\launch_ui.vbs" >NUL
REM Run install silently and log
powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%APPDIR%\scripts\install.ps1" > "%APPDIR%\logs\installer.log" 2>&1
REM Create Start Menu shortcut
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([IO.Path]::Combine($env:APPDATA,'Microsoft\\Windows\\Start Menu\\Programs','Dou SnapTrack.lnk')); $s.TargetPath=[IO.Path]::Combine($env:LocalAppData,'dou_snaptrack','launch_ui.vbs'); $s.WorkingDirectory=[IO.Path]::Combine($env:LocalAppData,'dou_snaptrack'); $s.Save()"
endlocal
