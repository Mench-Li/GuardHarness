# Auto-observation generator for Memory × Harness (PowerShell version)
# Usage: .claude/scripts/auto-observe.ps1 [commit-summary|test-failure|lint-failure|review-feedback]

param(
    [string]$Mode = "commit-summary"
)

$ObsDir = ".claude/memory/observations"
New-Item -ItemType Directory -Force -Path $ObsDir | Out-Null

$Timestamp = Get-Date -Format "yyyy-MM-dd-HHmmss"
$Date = Get-Date -Format "yyyy-MM-dd"

Write-Host "[auto-observe] Starting mode: $Mode"

function Generate-Frontmatter {
    param([string]$Type, [string]$Tags, [bool]$Compact = $false)
    $compactLine = if ($Compact) { "`nneeds_compaction: true" } else { "" }
    @"
---
date: $Date
type: $Type
generated_by: auto-observe
mode: $Mode
tags: [$Tags]$compactLine
---

"@ | Out-File -Append -FilePath $OutputFile -Encoding utf8
}

# Mode 1: Analyze recent commits for change patterns
function Mode-CommitSummary {
    $script:OutputFile = "$ObsDir/${Date}-commit-summary-${Timestamp}.md"
    Write-Host "[auto-observe] Generating commit-summary observation..."

    $LastCommitMsg = (git log -1 --pretty=format:"%s" 2>$null) -or "No commits"
    $ChangedFiles = (git diff --name-only HEAD~1 HEAD -- . 2>$null) -join "`n"
    $FileCount = ($ChangedFiles -split "`n" | Where-Object { $_ -ne "" }).Count

    $DocsChanged = ($ChangedFiles | Select-String -Pattern "\.(md|docs/)" -AllMatches).Matches.Count
    $TestsChanged = ($ChangedFiles | Select-String -Pattern "test|spec" -AllMatches).Matches.Count
    $ConfigChanged = ($ChangedFiles | Select-String -Pattern "\.(json|yaml|toml)" -AllMatches).Matches.Count

    # Size guard: if too many files, truncate and mark for compaction
    $NeedsCompaction = $false
    $FileList = $ChangedFiles
    if ($FileCount -gt 20) {
        $NeedsCompaction = $true
        $Truncated = ($ChangedFiles -split "`n" | Where-Object { $_ -ne "" } | Select-Object -First 20) -join "`n"
        $Remaining = $FileCount - 20
        $FileList = "$Truncated`n... and $Remaining more files"
    }

    Generate-Frontmatter -Type "commit-summary" -Tags "git,automation" -Compact $NeedsCompaction

    $Analysis = @"
## Commit Summary
- Message: $LastCommitMsg
- Files changed: $FileCount

## Change Pattern Analysis
"@

    if ($DocsChanged -gt 0) {
        $Analysis += "`n- Documentation updated alongside code changes"
    }
    if ($TestsChanged -gt 0) {
        $Analysis += "`n- Tests updated/modified in this commit"
    } else {
        $Analysis += "`n- No test files changed (potential gap)"
    }
    if ($ConfigChanged -gt 0) {
        $Analysis += "`n- Configuration files modified"
    }

    $Analysis += @"

## File Breakdown
```
$FileList
```

## Pattern Notes
- [Auto-generated] Review if this commit introduces a reusable pattern
- [Auto-generated] Check if commit scope aligns with plan task boundaries
"@

    $Analysis | Out-File -Append -FilePath $OutputFile -Encoding utf8
    Write-Host "[auto-observe] Generated: $OutputFile"
}

# Mode 2: Analyze test failures
function Mode-TestFailure {
    $script:OutputFile = "$ObsDir/${Date}-test-failure-${Timestamp}.md"
    Write-Host "[auto-observe] Generating test-failure observation..."

    $RecentFiles = (git diff --name-only HEAD~1 HEAD -- . 2>$null) -join "`n"
    if (-not $RecentFiles) { $RecentFiles = "unknown" }

    Generate-Frontmatter -Type "test-failure" -Tags "testing,automation"

    @"
## Test Failure Context
- Trigger: Automated detection after test run
- Recent changes:
```
$RecentFiles
```

## Potential Patterns
- [Auto-generated] Check if failure is in same area as recent changes
- [Auto-generated] Note if this is a recurring test failure pattern

## Manual Input Required
> Please review this observation and add:
> - Actual error message/output
> - Root cause analysis
> - Fix approach
"@ | Out-File -Append -FilePath $OutputFile -Encoding utf8

    Write-Host "[auto-observe] Generated: $OutputFile"
}

# Mode 3: Analyze lint failures
function Mode-LintFailure {
    $script:OutputFile = "$ObsDir/${Date}-lint-failure-${Timestamp}.md"
    Write-Host "[auto-observe] Generating lint-failure observation..."

    $RecentFiles = (git diff --name-only HEAD~1 HEAD -- . 2>$null) -join "`n"
    if (-not $RecentFiles) { $RecentFiles = "unknown" }

    Generate-Frontmatter -Type "lint-failure" -Tags "quality,automation"

    @"
## Lint/Quality Failure Context
- Trigger: Automated detection after lint run
- Recent changes:
```
$RecentFiles
```

## Potential Patterns
- [Auto-generated] Check if same lint rule is repeatedly violated
- [Auto-generated] Note if new files consistently miss lint standards

## Manual Input Required
> Please review this observation and add:
> - Specific lint errors
> - Whether pre-commit hooks could prevent this
"@ | Out-File -Append -FilePath $OutputFile -Encoding utf8

    Write-Host "[auto-observe] Generated: $OutputFile"
}

# Mode 4: Review feedback analysis
function Mode-ReviewFeedback {
    $script:OutputFile = "$ObsDir/${Date}-review-feedback-${Timestamp}.md"
    Write-Host "[auto-observe] Generating review-feedback observation..."

    Generate-Frontmatter -Type "code-review" -Tags "review,automation"

    @"
## Code Review Feedback
- Trigger: Post-review automated capture

## Capture Template
> Please fill in after review:
> - Review focus areas
> - Recurring issues flagged
> - Positive patterns noted
> - Suggestions for process improvement
"@ | Out-File -Append -FilePath $OutputFile -Encoding utf8

    Write-Host "[auto-observe] Generated: $OutputFile"
}

# Mode 5: Decision capture
function Mode-Decision {
    $script:OutputFile = "$ObsDir/${Date}-decision-${Timestamp}.md"
    Write-Host "[auto-observe] Generating decision observation..."

    $LastCommitMsg = (git log -1 --pretty=format:"%s" 2>$null) -or "No commits"

    Generate-Frontmatter -Type "decision" -Tags "architecture,decision"

    @"
## Decision Context
- Commit: $LastCommitMsg

## Options Considered
> [Auto-generated] Please fill in:
> - What options were considered?
> - What constraints existed?

## Decision
> [Auto-generated] What was chosen?

## Rationale
> [Auto-generated] Why was this option chosen over alternatives?

## Consequences
> [Auto-generated] What are the positive/negative consequences?
"@ | Out-File -Append -FilePath $OutputFile -Encoding utf8

    Write-Host "[auto-observe] Generated: $OutputFile"
}

# Mode 6: Entropy detection
function Mode-Entropy {
    $script:OutputFile = "$ObsDir/${Date}-entropy-${Timestamp}.md"
    Write-Host "[auto-observe] Generating entropy observation..."

    $RecentFiles = (git log --since="7 days ago" --name-only --pretty=format: -- . 2>$null) | Where-Object { $_ -ne "" } | Sort-Object -Unique

    $ManagerCount = @($RecentFiles | Where-Object { $_ -match "(manager|handler|processor|coordinator)" }).Count
    $InterfaceCount = @($RecentFiles | Where-Object { $_ -match "(interface|abstract|protocol|base)" }).Count
    $ConfigCount = @($RecentFiles | Where-Object { $_ -match "\.(json|yaml|yml|toml)$" }).Count

    $EntropyFlags = @()
    if ($ManagerCount -gt 2) { $EntropyFlags += "manager-proliferation($ManagerCount)" }
    if ($InterfaceCount -gt 2) { $EntropyFlags += "abstraction-explosion($InterfaceCount)" }
    if ($ConfigCount -gt 3) { $EntropyFlags += "config-nesting($ConfigCount)" }
    $FlagsStr = $EntropyFlags -join ", "

    Generate-Frontmatter -Type "entropy" -Tags "complexity,refactoring"

    $Indicators = if ($FlagsStr) { "- $FlagsStr" } else { "- No significant entropy indicators detected" }

    @"
## Entropy Detection
- Trigger: Automated complexity analysis
- Period: Last 7 days

## Detected Indicators
$Indicators

## The Smell
> [Auto-generated] What complexity pattern was introduced?

## Before / After
> [Auto-generated] Provide code examples if applicable

## Prevention Rule
> [Auto-generated] How to avoid this pattern in the future?
"@ | Out-File -Append -FilePath $OutputFile -Encoding utf8

    Write-Host "[auto-observe] Generated: $OutputFile"
}

# Mode 7: Taste preference capture
function Mode-Taste {
    $script:OutputFile = "$ObsDir/${Date}-taste-${Timestamp}.md"
    Write-Host "[auto-observe] Generating taste observation..."

    Generate-Frontmatter -Type "taste" -Tags "style,review"

    @"
## Taste Preference
- Trigger: Human correction or code review feedback

## The Preference
> [Auto-generated] What style preference was expressed?

## Source Context
> [Auto-generated] Where did this preference come from?
> - PR comment
> - Direct human correction
> - Explicit statement

## Examples
### Preferred
```
> [Auto-generated] Fill in preferred style
```

### Dispreferred
```
> [Auto-generated] Fill in dispreferred style
```

## When It Applies
> [Auto-generated] Always? Only in certain contexts?
"@ | Out-File -Append -FilePath $OutputFile -Encoding utf8

    Write-Host "[auto-observe] Generated: $OutputFile"
}

# Main dispatch
switch ($Mode) {
    "commit-summary"   { Mode-CommitSummary }
    "test-failure"     { Mode-TestFailure }
    "lint-failure"     { Mode-LintFailure }
    "review-feedback"  { Mode-ReviewFeedback }
    "decision"         { Mode-Decision }
    "entropy"          { Mode-Entropy }
    "taste"            { Mode-Taste }
    default {
        Write-Host "[auto-observe] Usage: .claude/scripts/auto-observe.ps1 [commit-summary|test-failure|lint-failure|review-feedback|decision|entropy|taste]"
        exit 1
    }
}

Write-Host "[auto-observe] Done."
