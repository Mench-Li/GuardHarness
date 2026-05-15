# Check if weekly memory reflection is due
# This script is called by the session_start hook in settings.json

$LastReflectionFile = ".claude/memory/.last-reflection"
$DaysBetweenReflections = 7

if (-not (Test-Path $LastReflectionFile)) {
    Write-Host "[Harness] Memory reflection has never been run. Consider running /reflect to initialize."
    exit 0
}

$LastDateStr = (Get-Content $LastReflectionFile -Raw).Trim()
$LastDate = $null

if (-not [DateTime]::TryParse($LastDateStr, [ref]$LastDate)) {
    Write-Host "[Harness] Could not parse last reflection date. Consider running /reflect."
    exit 0
}

$Now = Get-Date
$DiffDays = [math]::Floor(($Now - $LastDate).TotalDays)

if ($DiffDays -ge $DaysBetweenReflections) {
    Write-Host "[Harness] Weekly memory reflection is due (last run: $LastDateStr, $DiffDays days ago). Run /reflect to update patterns."
} else {
    Write-Host "[Harness] Memory reflection up to date (last run: $LastDateStr, $DiffDays days ago)."
}
