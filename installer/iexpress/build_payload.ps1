param(
  [string]$Root
)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $Root) { $Root = Resolve-Path (Join-Path $here '..\..') }
$payload = Join-Path $here 'payload'
$zip = Join-Path $payload 'project.zip'

if (Test-Path $zip) { Remove-Item -Force $zip }

# Include only essentials to avoid locking: src, scripts, pyproject.toml, README.md
$include = @()
$candidates = @()
$candidates += (Join-Path $Root 'src')
$candidates += (Join-Path $Root 'scripts')
$candidates += (Join-Path $Root 'pyproject.toml')
$candidates += (Join-Path $Root 'README.md')
foreach($p in $candidates){ if (Test-Path $p) { $include += $p } }

if ($include.Count -eq 0) { Write-Error 'No files to include in project.zip'; exit 1 }

# Stage files to avoid locking
$staging = Join-Path $here 'staging'
if (Test-Path $staging) { Remove-Item -Recurse -Force $staging }
$stageRoot = Join-Path $staging 'project'
New-Item -ItemType Directory -Path $stageRoot | Out-Null

foreach($p in $include){
  $dest = Join-Path $stageRoot ([IO.Path]::GetFileName($p))
  if ((Get-Item $p).PSIsContainer) {
    Copy-Item -Recurse -Force -ErrorAction SilentlyContinue $p $dest
  } else {
    Copy-Item -Force -ErrorAction SilentlyContinue $p $dest
  }
}

# Zip staged content
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory($stageRoot, $zip)
Write-Host "ZIP CREATED: $zip"

# Ensure SED output folder exists
$outDir = Join-Path $here 'dist'
if (-not (Test-Path $outDir)) { New-Item -ItemType Directory -Path $outDir | Out-Null }
