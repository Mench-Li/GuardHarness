# detect-entropy.ps1
# Detect complexity/entropy patterns in recent code changes
# Usage: .claude/scripts/detect-entropy.ps1 [days]

param(
    [int]$Days = 7
)

$EntropyDir = ".claude/memory/entropy"
$TmpDir = ".claude/memory/.tmp"
New-Item -ItemType Directory -Force -Path $EntropyDir, $TmpDir | Out-Null

$DateStr = Get-Date -Format "yyyy-MM-dd"
Write-Host "=== Entropy Detection Report ($DateStr) ==="
Write-Host "Analyzing last $Days days of changes"
Write-Host ""

# Check if git is available
try {
    $null = git rev-parse --git-dir 2>$null
} catch {
    Write-Host "Not a git repository. Skipping entropy detection."
    exit 0
}

$Cutoff = (Get-Date).AddDays(-$Days).ToString("yyyy-MM-dd")
$ChangedFiles = git log --since="$Cutoff" --name-only --pretty=format: -- . 2>$null | Where-Object { $_ -ne "" } | Sort-Object -Unique

if (-not $ChangedFiles) {
    Write-Host "No changes found in the last $Days days."
    exit 0
}

$FileCount = @($ChangedFiles).Count
Write-Host "Found $FileCount changed files"
Write-Host ""

# Heuristic 1: Manager/Handler/Processor/Coordinator proliferation
$ManagerFiles = $ChangedFiles | Where-Object { $_ -match "(manager|handler|processor|coordinator|service)" }
$UniqueManagers = $ManagerFiles | Sort-Object -Unique
if ($UniqueManagers.Count -gt 2) {
    Write-Host "Warning manager-proliferation detected"
    Write-Host "   Found $($UniqueManagers.Count) unique manager/handler/processor/coordinator files"
    Write-Host "   Indicators:"
    $UniqueManagers | ForEach-Object { Write-Host "     - $_" }
    Write-Host ""
}

# Heuristic 2: Config churn
$ConfigFiles = $ChangedFiles | Where-Object { $_ -match "\.(json|yaml|yml|toml)$" }
if ($ConfigFiles) {
    $ConfigCount = @($ConfigFiles).Count
    Write-Host "Config files changed: $ConfigCount"
    $ConfigFiles | Select-Object -First 5 | ForEach-Object { Write-Host "     - $_" }
    if ($ConfigCount -gt 5) {
        Write-Host "   Warning High config churn detected -- check for config-nesting entropy"
    }
    Write-Host ""
}

# Heuristic 3: New file explosion
$NewFiles = git log --since="$Cutoff" --diff-filter=A --name-only --pretty=format: -- . 2>$null | Where-Object { $_ -ne "" } | Sort-Object -Unique
if ($NewFiles) {
    $NewCount = @($NewFiles).Count
    if ($NewCount -gt 10) {
        Write-Host "Warning abstraction-explosion indicator"
        Write-Host "   $NewCount new files created in $Days days"
        Write-Host "   Check if these are speculative abstractions (interfaces with one implementation)"
        Write-Host ""
    }
}

# Heuristic 4: Compare against existing entropy patterns
$Existing = Get-ChildItem -Path $EntropyDir -Filter "*.md" -ErrorAction SilentlyContinue
if ($Existing.Count -gt 0) {
    Write-Host "Existing entropy patterns: $($Existing.Count)"
    Write-Host "Comparing against known patterns..."
    foreach ($ef in $Existing) {
        $content = Get-Content $ef.FullName -Raw
        $categoryMatch = [regex]::Match($content, "(?m)^category:\s*(.+)$")
        $category = if ($categoryMatch.Success) { $categoryMatch.Groups[1].Value.Trim().Trim('"', "'") } else { "" }
        $keywords = switch ($category) {
            "manager-proliferation" { "manager|handler|processor|coordinator" }
            "config-nesting" { "config|settings|yaml|json" }
            "abstraction-explosion" { "abstract|interface|base|factory" }
            "speculative-interface" { "interface|protocol|abstract" }
            "indirection-creep" { "proxy|wrapper|adapter|delegate" }
            default { "" }
        }
        if ($keywords) {
            $matches = @($ChangedFiles | Where-Object { $_ -match $keywords }).Count
            if ($matches -gt 0) {
                Write-Host "   Matches existing entropy pattern: $category ($matches files)"
            }
        }
    }
    Write-Host ""
}

Write-Host "=== End of Report ==="
