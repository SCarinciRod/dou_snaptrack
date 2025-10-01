param(
  [string]$WorkDir
)

$ErrorActionPreference = 'Stop'

if (-not $WorkDir) {
  $WorkDir = Split-Path -Parent $MyInvocation.MyCommand.Path
  $WorkDir = Resolve-Path (Join-Path $WorkDir '..')
}

# Ensure we run from project root
Set-Location $WorkDir

# Create logs dir
$logs = Join-Path $WorkDir 'logs'
if (-not (Test-Path $logs)) { New-Item -ItemType Directory -Path $logs | Out-Null }
$logFile = Join-Path $logs 'installer.log'

# Run install.ps1 hidden, capture output
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = 'powershell.exe'
$psi.Arguments = '-NoProfile -ExecutionPolicy Bypass -File "scripts\\install.ps1"'
$psi.WorkingDirectory = $WorkDir
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$psi.UseShellExecute = $false
$psi.CreateNoWindow = $true

$p = New-Object System.Diagnostics.Process
$p.StartInfo = $psi
$p.Start() | Out-Null
$stdOut = $p.StandardOutput.ReadToEnd()
$stdErr = $p.StandardError.ReadToEnd()
$p.WaitForExit()

$stdOut | Out-File -Encoding UTF8 -FilePath $logFile -Append
$stdErr | Out-File -Encoding UTF8 -FilePath $logFile -Append

if ($p.ExitCode -ne 0) {
  Write-Host "Installer failed. See $logFile" -ForegroundColor Red
  exit $p.ExitCode
}

Write-Host 'Installer finished successfully.' -ForegroundColor Green
exit 0
