; Inno Setup Script for Dou SnapTrack (per-user)
; Build with Inno Setup Compiler (https://jrsoftware.org/isinfo.php)

#define MyAppName "Dou SnapTrack"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "SCarinciRod"
#define MyAppURL "https://github.com/SCarinciRod/dou_snaptrack"
#define MyAppExeName "launch_ui_managed.vbs"

[Setup]
AppId={{9C2B3A9D-33B6-4C7F-9F61-8E4B6A0D0D47}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={localappdata}\dou_snaptrack
DisableProgramGroupPage=yes
OutputDir=dist
OutputBaseFilename=DouSnapTrack-Setup
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=lowest
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma
SolidCompression=yes

[Languages]
Name: "portuguese"; MessagesFile: "compiler:Languages\Portuguese.isl"

[Files]
; Copy entire project (you can narrow this for production)
Source: "..\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion
; Ensure installer auxiliaries are present (relative to this .iss file)
Source: ".\run_silent_install.ps1"; DestDir: "{app}\installer"; Flags: ignoreversion
Source: ".\launch_ui.vbs"; DestDir: "{app}"; Flags: ignoreversion
Source: ".\launch_ui_managed.vbs"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\scripts\run-ui-managed.ps1"; DestDir: "{app}\scripts"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; WorkingDir: "{app}"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na Área de Trabalho"; GroupDescription: "Atalhos:"; Flags: unchecked

[Run]
; Run the silent installer wrapper after files are copied
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\installer\run_silent_install.ps1"" -WorkDir ""{app}"""; Flags: runhidden; StatusMsg: "Configurando ambiente..."

[UninstallDelete]
; Optional: remove venv to save space
Type: filesandordirs; Name: "{app}\.venv"
