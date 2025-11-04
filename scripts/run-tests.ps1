param(
  [ValidateSet('all','smoke','mapping')]
  [string]$Suite = 'all',
  [string]$Python = ''
)

# Choose python
if (-not $Python) {
  $Python = (Get-Command python -ErrorAction SilentlyContinue).Source
  if (-not $Python) { $Python = (Get-Command py -ErrorAction SilentlyContinue).Source }
  if (-not $Python) { $Python = $PSCommandPath; $Python = '' }
}

$root = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$runner = Join-Path $root 'tests\run_tests.py'

if (-not (Test-Path $runner)) {
  Write-Error "Runner nao encontrado: $runner"
  exit 1
}

$cmd = "& `"$Python`" `"$runner`" --suite $Suite"
if ($Python) {
  Write-Host "[RUN] $cmd"
  & $Python $runner --suite $Suite
} else {
  Write-Host "[RUN] python $runner --suite $Suite"
  python $runner --suite $Suite
}
