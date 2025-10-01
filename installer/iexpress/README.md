This folder contains an IExpress-based installer (built into Windows) so you can generate a self-extracting EXE without installing Inno Setup.

What it does
- Packages the project folder and a bootstrap batch
- On extraction, runs the bootstrap to execute PowerShell silently and install the app under %LocalAppData%\dou_snaptrack
- Creates Start Menu shortcut via PowerShell and a VBScript launcher to hide consoles

How to build
- Use the IExpress Wizard (iexpress.exe) and import the provided SED file, or build via command line: `iexpress /N installer.sed`

Notes
- IExpress has simpler UI (basic wizard). It will still show a minimal progress dialog. For a full modern wizard, prefer Inno Setup.
- Corporate restrictions may block unsigned EXEs or script execution; in that case, coordinate with IT for code signing or whitelisting.
