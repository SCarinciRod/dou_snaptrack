param([string]$file)
$tokens=$null; $errors=$null
[void][System.Management.Automation.Language.Parser]::ParseFile($file, [ref]$tokens, [ref]$errors)
if ($errors -and $errors.Count -gt 0) {
  Write-Host "Found $($errors.Count) parse errors:"
  foreach($e in $errors){
    Write-Host ("Line {0}, Col {1}: {2}" -f $e.Extent.StartLineNumber, $e.Extent.StartColumnNumber, $e.Message)
    $line = (Get-Content $file -TotalCount $e.Extent.StartLineNumber)[-1]
    Write-Host "--> $line"
  }
} else { Write-Host "No parse errors." }
