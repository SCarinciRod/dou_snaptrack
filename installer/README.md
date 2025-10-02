This folder contains the Windows GUI installer definition using Inno Setup.

Overview
- Installs a private copy of dou_snaptrack under %LocalAppData%\dou_snaptrack (per-user only, no admin required)
- Runs scripts\install.ps1 silently to set up Python 3.11, a venv, and dependencies
- Creates Start Menu and optional Desktop shortcuts to "Dou SnapTrack" (launches the Streamlit UI)

Files
- DouSnapTrack.iss: Inno Setup script (build with the Inno Setup Compiler)
- run_silent_install.ps1: wrapper that runs install.ps1 hidden and writes logs
- launch_ui.vbs: double-click launcher that starts scripts\run-ui.ps1 without showing a console

Build steps (Inno Setup)
1) Install Inno Setup (https://jrsoftware.org/isinfo.php)
2) Open DouSnapTrack.iss in Inno Setup Compiler
3) Press Build (F9). The output .exe will be in the OutputDir configured in the script

Notes
- The installer does NOT download browsers; the app uses system Chrome/Edge
- The wizard runs per-user; no admin is required. If corporate policies block PowerShell execution, ensure ExecutionPolicy allows local scripts (the installer sets it for the child process only)
- After install, you can check "Executar Dou SnapTrack agora" to launch immediately. Shortcuts are created in Start Menu and optionally on Desktop.
- Offline variant: you can extend run_silent_install.ps1 to use pre-bundled wheels/Python
