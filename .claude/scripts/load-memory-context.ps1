# load-memory-context.ps1
# Load all 5 memory layers + existing patterns, sorted by priority
# Usage: .claude/scripts/load-memory-context.ps1 [skill-name] [domain]

param(
    [string]$Skill = "general",
    [string]$Domain = "general"
)

Write-Host "=== Loading Memory Context for: $Skill (domain: $Domain) ==="
Write-Host ""

# 1. Invariants (constitutional rules first)
$InvDir = ".claude/memory/invariants"
if (Test-Path $InvDir) {
    $InvFiles = @()
    $InvFiles += Get-ChildItem -Path $InvDir -Filter "general-*.md" -ErrorAction SilentlyContinue
    if ($Domain -ne "general") {
        $InvFiles += Get-ChildItem -Path $InvDir -Filter "${Domain}-*.md" -ErrorAction SilentlyContinue
    }
    $InvFiles = $InvFiles | Where-Object { $_ }
    if ($InvFiles.Count -gt 0) {
        Write-Host "## Architectural Invariants ($($InvFiles.Count))"
        Write-Host "These rules MUST NOT be violated under any circumstances."
        Write-Host ""
        foreach ($f in $InvFiles) {
            $content = Get-Content $f.FullName -Raw
            $nameMatch = [regex]::Match($content, "(?m)^name:\s*(.+)$")
            $name = if ($nameMatch.Success) { $nameMatch.Groups[1].Value.Trim().Trim('"', "'") } else { $f.BaseName }
            $sevMatch = [regex]::Match($content, "(?m)^violation_severity:\s*(.+)$")
            $severity = if ($sevMatch.Success) { $sevMatch.Groups[1].Value.Trim().Trim('"', "'") } else { "" }
            $ruleMatch = [regex]::Match($content, "(?ms)^## The Rule\s*(.+?)^## ")
            $rule = if ($ruleMatch.Success) { $ruleMatch.Groups[1].Value.Trim() } else { "" }
            Write-Host "### [$severity] $name"
            Write-Host "$rule"
            Write-Host ""
        }
    }
}

# 2. Active decisions
$DecDir = ".claude/memory/decisions"
if (Test-Path $DecDir) {
    $DecFiles = Get-ChildItem -Path $DecDir -Filter "*.md" -ErrorAction SilentlyContinue
    $ActiveFiles = $DecFiles | Where-Object {
        $content = Get-Content $_.FullName -Raw
        [regex]::Match($content, "(?m)^status:\s*active\s*$").Success
    }
    if ($ActiveFiles.Count -gt 0) {
        Write-Host "## Active Decisions ($($ActiveFiles.Count) total)"
        Write-Host "These decisions constrain the design space."
        Write-Host ""
        foreach ($f in $ActiveFiles) {
            $content = Get-Content $f.FullName -Raw
            $titleMatch = [regex]::Match($content, "^# Decision:\s*(.+)$", [System.Text.RegularExpressions.RegexOptions]::Multiline)
            $title = if ($titleMatch.Success) { $titleMatch.Groups[1].Value.Trim() } else { $f.BaseName }
            $decMatch = [regex]::Match($content, "(?ms)^## (Decision|决策)\s*(.+?)^## ")
            $decision = if ($decMatch.Success) { ($decMatch.Groups[2].Value -split "`n" | Select-Object -First 5) -join "`n" } else { "" }
            Write-Host "### $title"
            Write-Host "$decision"
            Write-Host ""
        }
    }
}

# 3. Failure lessons
$FailDir = ".claude/memory/failures"
if (Test-Path $FailDir) {
    $FailFiles = Get-ChildItem -Path $FailDir -Filter "*.md" -ErrorAction SilentlyContinue
    if ($FailFiles.Count -gt 0) {
        Write-Host "## Failure Lessons ($($FailFiles.Count) total)"
        Write-Host "Learn from past incidents to avoid recurrence."
        Write-Host ""
        foreach ($f in ($FailFiles | Select-Object -First 5)) {
            $content = Get-Content $f.FullName -Raw
            $titleMatch = [regex]::Match($content, "^# Failure:\s*(.+)$", [System.Text.RegularExpressions.RegexOptions]::Multiline)
            $title = if ($titleMatch.Success) { $titleMatch.Groups[1].Value.Trim() } else { $f.BaseName }
            $learnMatch = [regex]::Match($content, "(?ms)^## (What We Learned|我们学到了什么)\s*(.+?)^## ")
            $learned = if ($learnMatch.Success) { ($learnMatch.Groups[2].Value -split "`n" | Select-Object -First 5) -join "`n" } else { "" }
            Write-Host "### $title"
            Write-Host "$learned"
            Write-Host ""
        }
    }
}

# 4. Entropy patterns
$EntDir = ".claude/memory/entropy"
if (Test-Path $EntDir) {
    $EntFiles = Get-ChildItem -Path $EntDir -Filter "*.md" -ErrorAction SilentlyContinue
    if ($EntFiles.Count -gt 0) {
        Write-Host "## Entropy Patterns to Avoid ($($EntFiles.Count))"
        Write-Host "These complexity anti-patterns have been observed before."
        Write-Host ""
        foreach ($f in $EntFiles) {
            $content = Get-Content $f.FullName -Raw
            $titleMatch = [regex]::Match($content, "^# Entropy Pattern:\s*(.+)$", [System.Text.RegularExpressions.RegexOptions]::Multiline)
            $title = if ($titleMatch.Success) { $titleMatch.Groups[1].Value.Trim() } else { $f.BaseName }
            $smellMatch = [regex]::Match($content, "(?ms)^## (The Smell|臭味)\s*(.+?)^## ")
            $smell = if ($smellMatch.Success) { ($smellMatch.Groups[2].Value -split "`n" | Select-Object -First 3) -join "`n" } else { "" }
            Write-Host "### $title"
            Write-Host "$smell"
            Write-Host ""
        }
    }
}

# 5. Confirmed taste
$TasteDirPath = ".claude/memory/taste"
if (Test-Path $TasteDirPath) {
    $TasteFiles = Get-ChildItem -Path $TasteDirPath -Filter "*.md" -ErrorAction SilentlyContinue
    $Confirmed = $TasteFiles | Where-Object {
        $content = Get-Content $_.FullName -Raw
        [regex]::Match($content, "(?m)^confidence:\s*confirmed\s*$").Success
    }
    if ($Confirmed.Count -gt 0) {
        Write-Host "## Confirmed Taste Preferences ($($Confirmed.Count))"
        Write-Host "These preferences have been observed multiple times."
        Write-Host ""
        foreach ($f in $Confirmed) {
            $content = Get-Content $f.FullName -Raw
            $titleMatch = [regex]::Match($content, "^# Taste:\s*(.+)$", [System.Text.RegularExpressions.RegexOptions]::Multiline)
            $title = if ($titleMatch.Success) { $titleMatch.Groups[1].Value.Trim() } else { $f.BaseName }
            $prefMatch = [regex]::Match($content, "(?ms)^## (The Preference|偏好)\s*(.+?)^## ")
            $pref = if ($prefMatch.Success) { ($prefMatch.Groups[2].Value -split "`n" | Select-Object -First 3) -join "`n" } else { "" }
            Write-Host "### $title"
            Write-Host "$pref"
            Write-Host ""
        }
    }
}

# 6. Established patterns
$PatDir = ".claude/memory/patterns"
if (Test-Path $PatDir) {
    $PatFiles = Get-ChildItem -Path $PatDir -Filter "*.md" -ErrorAction SilentlyContinue
    if ($PatFiles.Count -gt 0) {
        Write-Host "## Established Patterns ($($PatFiles.Count))"
        Write-Host ""
        foreach ($f in ($PatFiles | Select-Object -First 5)) {
            $content = Get-Content $f.FullName -Raw
            $titleMatch = [regex]::Match($content, "^# (.+)$", [System.Text.RegularExpressions.RegexOptions]::Multiline)
            $title = if ($titleMatch.Success) { $titleMatch.Groups[1].Value.Trim() } else { $f.BaseName }
            $patMatch = [regex]::Match($content, "(?ms)^## Pattern\s*(.+?)^## ")
            $pattern = if ($patMatch.Success) { ($patMatch.Groups[1].Value -split "`n" | Select-Object -First 5) -join "`n" } else { "" }
            Write-Host "### $title"
            Write-Host "$pattern"
            Write-Host ""
        }
    }
}

Write-Host "=== End of Memory Context ==="
