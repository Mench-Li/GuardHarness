# detect-memory-conflicts.ps1
# Detect potential conflicts between project patterns and global axioms
# Usage: .claude/scripts/detect-memory-conflicts.ps1

$PatternsDir = ".claude/memory/patterns"
$InvariantsDir = ".claude/memory/invariants"
$DecisionsDir = ".claude/memory/decisions"
$TasteDir = ".claude/memory/taste"
$EntropyDir = ".claude/memory/entropy"
$AxiomsFile = ".claude/memory/user/axioms.md"
$TmpDir = ".claude/memory/.tmp"
New-Item -ItemType Directory -Force -Path $TmpDir | Out-Null

$DateStr = Get-Date -Format "yyyy-MM-dd"
Write-Host "=== Memory Conflict Detection Report ($DateStr) ==="
Write-Host ""

# Collect files
$PatternFiles = if (Test-Path $PatternsDir) { Get-ChildItem -Path $PatternsDir -Filter "*.md" -Recurse -ErrorAction SilentlyContinue | Sort-Object FullName } else { @() }
$InvariantFiles = if (Test-Path $InvariantsDir) { Get-ChildItem -Path $InvariantsDir -Filter "*.md" -Recurse -ErrorAction SilentlyContinue | Sort-Object FullName } else { @() }
$DecisionFiles = if (Test-Path $DecisionsDir) { Get-ChildItem -Path $DecisionsDir -Filter "*.md" -Recurse -ErrorAction SilentlyContinue | Sort-Object FullName } else { @() }
$TasteFiles = if (Test-Path $TasteDir) { Get-ChildItem -Path $TasteDir -Filter "*.md" -Recurse -ErrorAction SilentlyContinue | Sort-Object FullName } else { @() }
$EntropyFiles = if (Test-Path $EntropyDir) { Get-ChildItem -Path $EntropyDir -Filter "*.md" -Recurse -ErrorAction SilentlyContinue | Sort-Object FullName } else { @() }

$AxiomCount = 0
if (Test-Path $AxiomsFile) {
    $AxiomCount = ([regex]::Matches((Get-Content $AxiomsFile -Raw), "^## ")).Count
}

Write-Host "Patterns scanned: $($PatternFiles.Count)"
Write-Host "Invariants scanned: $($InvariantFiles.Count)"
Write-Host "Decisions scanned: $($DecisionFiles.Count)"
Write-Host "Taste scanned: $($TasteFiles.Count)"
Write-Host "Entropy scanned: $($EntropyFiles.Count)"
Write-Host "Axioms scanned: $AxiomCount"
Write-Host ""

if ($PatternFiles.Count -eq 0 -and $AxiomCount -eq 0 -and $InvariantFiles.Count -eq 0) {
    Write-Host "No patterns, axioms, or invariants found. Nothing to check."
    Remove-Item -Recurse -Force $TmpDir -ErrorAction SilentlyContinue
    exit 0
}

function Get-FrontmatterValue {
    param([string]$Content, [string]$Key)
    $pattern = "(?m)^$Key\s*:\s*(.+)$"
    $match = [regex]::Match($Content, $pattern)
    if ($match.Success) { return $match.Groups[1].Value.Trim().Trim('"', "'") }
    return ""
}

function Extract-Semantics {
    param([string]$Text, [string]$Source, [string]$Name)
    $lower = $Text.ToLower()
    $action = "neutral"
    if ($lower -match "(must|should|recommend|use|adopt|choose|prefer|always|all)") { $action = "positive" }
    elseif ($lower -match "(avoid|don't|prohibit|not|disable|never)") { $action = "negative" }

    $techKeywords = @("mock","test","database","api","rest","graphql","grpc","oauth","jwt","session","cache","redis","docker","kubernetes","sql","nosql","mongo","postgres","mysql","typescript","javascript","python","go","rust","java","react","vue","angular","svelte","fastapi","django","flask","spring","express","nestjs")
    $found = @()
    foreach ($kw in $techKeywords) {
        if ($lower -match "\b$kw\b") { $found += $kw }
    }
    $objects = ($found | Sort-Object -Unique) -join ","

    $hashBytes = [System.Text.Encoding]::UTF8.GetBytes(($Text.Substring(0, [Math]::Min(80, $Text.Length))))
    $hash = [System.BitConverter]::ToString([System.Security.Cryptography.MD5]::Create().ComputeHash($hashBytes)).Replace("-", "").ToLower()

    return [PSCustomObject]@{
        Source = $Source
        Name = $Name
        Action = $action
        Objects = $objects
        Hash = $hash
    }
}

$Semantics = @()

foreach ($f in $PatternFiles) {
    $content = Get-Content $f.FullName -Raw
    $name = Get-FrontmatterValue -Content $content -Key "name"
    if (-not $name) { $name = $f.BaseName }
    $patternText = ""
    $pmatch = [regex]::Match($content, "(?ms)^## Pattern\s*(.+?)^## ")
    if ($pmatch.Success) {
        $patternText = $pmatch.Groups[1].Value
    } else {
        $patternText = [regex]::Replace($content, "(?ms)^---\s*.*?\s*---\s*", "")
    }
    $Semantics += Extract-Semantics -Text $patternText -Source "pattern:$($f.FullName)" -Name $name
}

if (Test-Path $AxiomsFile) {
    $axiomContent = Get-Content $AxiomsFile -Raw
    $blocks = [regex]::Matches($axiomContent, "(?ms)^## (.+?)(?=^## |$)")
    foreach ($block in $blocks) {
        $lines = $block.Value -split "`n"
        $axiomName = $lines[0].Trim().TrimStart('#').Trim()
        $axiomText = ($lines | Select-Object -Skip 1) -join "`n"
        if ($axiomName) {
            $Semantics += Extract-Semantics -Text $axiomText -Source "axiom:$AxiomsFile" -Name $axiomName
        }
    }
}

# Conflict detection
$Conflicts = @()
for ($i = 0; $i -lt $Semantics.Count; $i++) {
    for ($j = 0; $j -lt $Semantics.Count; $j++) {
        $s1 = $Semantics[$i]
        $s2 = $Semantics[$j]
        if ($s1.Source -like "pattern:*" -and $s2.Source -like "axiom:*") {
            $objs1 = $s1.Objects -split "," | Where-Object { $_ }
            $objs2 = $s2.Objects -split "," | Where-Object { $_ }
            $shared = @()
            foreach ($a in $objs1) {
                foreach ($b in $objs2) {
                    if ($a -eq $b) { $shared += $a }
                }
            }
            $shared = $shared | Select-Object -Unique
            if ($shared.Count -gt 0) {
                $sharedStr = $shared -join ","
                if ($s1.Action -ne $s2.Action -and $s1.Action -ne "neutral" -and $s2.Action -ne "neutral") {
                    $Conflicts += [PSCustomObject]@{ Type="CONFLICT"; P1=$s1.Name; S1=$s1.Source; A1=$s1.Action; P2=$s2.Name; S2=$s2.Source; A2=$s2.Action; Objs=$sharedStr; Note="opposite action" }
                } elseif ($s1.Action -eq $s2.Action -and $s1.Action -ne "neutral") {
                    $Conflicts += [PSCustomObject]@{ Type="ALIGN"; P1=$s1.Name; S1=$s1.Source; A1=$s1.Action; P2=$s2.Name; S2=$s2.Source; A2=$s2.Action; Objs=$sharedStr; Note="aligned" }
                }
            }
        }
    }
}

# Invariant violations
Write-Host "=== Invariant Violations ==="
Write-Host ""
if ($InvariantFiles.Count -gt 0) {
    foreach ($inv_f in $InvariantFiles) {
        $content = Get-Content $inv_f.FullName -Raw
        $invName = Get-FrontmatterValue -Content $content -Key "name"
        $invRuleMatch = [regex]::Match($content, "(?ms)^## The Rule\s*(.+?)^## ")
        $invRule = if ($invRuleMatch.Success) { ($invRuleMatch.Groups[1].Value -split "`n" | Select-Object -First 1).Trim() } else { "" }
        $invDomain = Get-FrontmatterValue -Content $content -Key "domain"
        foreach ($pat_f in $PatternFiles) {
            Write-Host "Invariant check: $invName (domain: $invDomain)"
            Write-Host "   Rule: $invRule"
            Write-Host "   Review pattern: $($pat_f.Name)"
            Write-Host "   Action: Verify pattern does not violate invariant"
            Write-Host ""
        }
    }
} else {
    Write-Host "No invariants to check against."
}

# Taste vs Axiom
Write-Host "=== Taste vs Axiom Conflicts ==="
Write-Host ""
if ($TasteFiles.Count -gt 0 -and $AxiomCount -gt 0) {
    Write-Host "Taste preferences should not override axioms."
    Write-Host "   Manual review recommended if taste contradicts architectural rules."
    Write-Host ""
} else {
    Write-Host "No taste/axiom conflicts to check."
}

# Entropy warnings
Write-Host "=== Entropy Pattern Warnings ==="
Write-Host ""
if ($EntropyFiles.Count -gt 0) {
    foreach ($ent_f in $EntropyFiles) {
        $content = Get-Content $ent_f.FullName -Raw
        $entCategory = Get-FrontmatterValue -Content $content -Key "category"
        $entTitleMatch = [regex]::Match($content, "^# Entropy Pattern:\s*(.+)$", [System.Text.RegularExpressions.RegexOptions]::Multiline)
        $entTitle = if ($entTitleMatch.Success) { $entTitleMatch.Groups[1].Value.Trim() } else { "" }
        Write-Host "Warning Entropy pattern registered: $entTitle ($entCategory)"
        Write-Host "   New patterns should be checked against this anti-pattern."
        Write-Host ""
    }
} else {
    Write-Host "No entropy patterns registered."
}

# Pattern vs Axiom conflicts
Write-Host "=== Pattern vs Axiom Conflicts ==="
Write-Host ""
$ConflictsList = $Conflicts | Where-Object { $_.Type -eq "CONFLICT" }
if ($ConflictsList.Count -gt 0) {
    foreach ($c in ($ConflictsList | Sort-Object Objs)) {
        Write-Host "Warning Conflict: $($c.P1) <-> $($c.P2)"
        Write-Host "   Shared objects: $($c.Objs)"
        Write-Host "   Pattern action: $($c.A1) | Axiom action: $($c.A2)"
        Write-Host "   Files: $($c.S1 -replace '^pattern:') vs $($c.S2 -replace '^axiom:')"
        Write-Host ""
    }
} else {
    Write-Host "No pattern-vs-axiom conflicts detected."
}

# Alignments
Write-Host "=== Alignments Found ==="
Write-Host ""
$Alignments = $Conflicts | Where-Object { $_.Type -eq "ALIGN" }
if ($Alignments.Count -gt 0) {
    foreach ($c in ($Alignments | Sort-Object Objs)) {
        Write-Host "Alignment: $($c.P1) <-> $($c.P2)"
        Write-Host "   Shared objects: $($c.Objs)"
        Write-Host "   Action: $($c.A1)"
        Write-Host ""
    }
} else {
    Write-Host "No alignments detected."
}

# Coverage analysis
Write-Host "=== Object Coverage Analysis ==="
Write-Host ""
$PatternObjs = ($Semantics | Where-Object { $_.Source -like "pattern:*" } | ForEach-Object { $_.Objects -split "," } | Where-Object { $_ } | Sort-Object -Unique) -join "`n"
$AxiomObjs = ($Semantics | Where-Object { $_.Source -like "axiom:*" } | ForEach-Object { $_.Objects -split "," } | Where-Object { $_ } | Sort-Object -Unique) -join "`n"

if ($PatternObjs -and $AxiomObjs) {
    $pSet = $PatternObjs -split "`n" | Where-Object { $_ }
    $aSet = $AxiomObjs -split "`n" | Where-Object { $_ }
    $uncovered = $pSet | Where-Object { $_ -notin $aSet }
    if ($uncovered) {
        Write-Host "Objects in patterns but not covered by axioms: $($uncovered -join ', ')"
        Write-Host "Suggestion: Consider upgrading patterns covering these objects to global axioms."
    } else {
        Write-Host "All pattern objects are covered by axioms."
    }
} else {
    Write-Host "Insufficient data for coverage analysis."
}

Remove-Item -Recurse -Force $TmpDir -ErrorAction SilentlyContinue
Write-Host ""
Write-Host "=== End of Report ==="
