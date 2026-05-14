# check-invariants.ps1
# Load architectural invariants for a given domain
# Usage: .claude/scripts/check-invariants.ps1 [domain]

param(
    [string]$Domain = "general"
)

$InvariantsDir = ".claude/memory/invariants"

Write-Host "=== Invariant Check for domain: $Domain ==="
Write-Host ""

if (-not (Test-Path $InvariantsDir)) {
    Write-Host "No invariants directory found."
    exit 0
}

function Get-FrontmatterValue {
    param([string]$Content, [string]$Key)
    $pattern = "(?m)^$Key\s*:\s*(.+)$"
    $match = [regex]::Match($Content, $pattern)
    if ($match.Success) { return $match.Groups[1].Value.Trim().Trim('"', "'") }
    return ""
}

function Get-RuleSection {
    param([string]$Content)
    $pattern = "(?ms)^## The Rule\s*(.+?)^## "
    $match = [regex]::Match($Content + "`n## END", $pattern)
    if ($match.Success) {
        $rule = $match.Groups[1].Value.Trim()
        $lines = $rule -split "`n" | ForEach-Object { $_.Trim() } | Select-Object -First 3
        return $lines -join "`n"
    }
    return ""
}

$GeneralCount = 0
$DomainCount = 0

# Load general invariants
$GeneralFiles = Get-ChildItem -Path $InvariantsDir -Filter "general-*.md" -ErrorAction SilentlyContinue
foreach ($f in $GeneralFiles) {
    $GeneralCount++
    $content = Get-Content $f.FullName -Raw
    $name = Get-FrontmatterValue -Content $content -Key "name"
    $severity = Get-FrontmatterValue -Content $content -Key "violation_severity"
    $rule = Get-RuleSection -Content $content
    Write-Host "[$severity] $name"
    Write-Host "$rule"
    Write-Host ""
}

# Load domain-specific invariants
if ($Domain -ne "general") {
    $DomainFiles = Get-ChildItem -Path $InvariantsDir -Filter "${Domain}-*.md" -ErrorAction SilentlyContinue
    foreach ($f in $DomainFiles) {
        if ($f.Name -like "general-*") { continue }
        $DomainCount++
        $content = Get-Content $f.FullName -Raw
        $name = Get-FrontmatterValue -Content $content -Key "name"
        $severity = Get-FrontmatterValue -Content $content -Key "violation_severity"
        $rule = Get-RuleSection -Content $content
        Write-Host "[$severity] $name"
        Write-Host "$rule"
        Write-Host ""
    }
}

Write-Host "Loaded $GeneralCount general invariants, $DomainCount domain invariants."
