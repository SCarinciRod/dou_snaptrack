Build steps for IExpress-based installer:

1) Prepare payload\project.zip with the project content you want to deliver (exclude .git, .venv, dist, logs, __pycache__)
   - You can create it with PowerShell:
     Compress-Archive -Force -Path ..\..\* -DestinationPath .\project.zip -CompressionLevel Optimal \
       -Exclude *.git*, .venv*, dist*, logs*, __pycache__*

2) Ensure payload contains:
   - setup.cmd (provided)
   - project.zip (from step 1)
   - install.ps1 (copied from scripts/install.ps1)
   - run-ui.ps1 (copied from scripts/run-ui.ps1)
   - launch_ui.vbs (copy from installer/launch_ui.vbs)

3) Build the SFX with IExpress (built-in to Windows):
   - GUI: Run `iexpress.exe`, choose "Open existing SED", select installer.sed, then Finish
   - CLI: `iexpress /N installer.sed`

4) Distribute dist\DouSnapTrack-Setup-iexpress.exe to users.
