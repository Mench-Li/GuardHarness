# cluster-observations.ps1
# Keyword clustering of recent observations to assist pattern extraction
# Usage: .claude/scripts/cluster-observations.ps1 [days]

param(
    [int]$Days = 30
)

$ObsDir = ".claude/memory/observations"
$TmpDir = ".claude/memory/.tmp"
New-Item -ItemType Directory -Force -Path $TmpDir | Out-Null

$DateStr = Get-Date -Format "yyyy-MM-dd"
Write-Host "=== Observation Clustering Report ($DateStr) ==="
Write-Host "Scanning last $Days days in $ObsDir"
Write-Host ""

$Cutoff = (Get-Date).AddDays(-$Days)
$Files = if (Test-Path $ObsDir) {
    Get-ChildItem -Path $ObsDir -Filter "*.md" -Recurse -ErrorAction SilentlyContinue | Where-Object { $_.LastWriteTime -ge $Cutoff } | Sort-Object FullName
} else { @() }

if ($Files.Count -eq 0) {
    Write-Host "No observations found in the last $Days days."
    Remove-Item -Recurse -Force $TmpDir -ErrorAction SilentlyContinue
    exit 0
}

Write-Host "Found $($Files.Count) observation files"
Write-Host ""

function Get-FrontmatterValue {
    param([string]$Content, [string]$Key)
    $pattern = "(?m)^$Key\s*:\s*(.+)$"
    $match = [regex]::Match($Content, $pattern)
    if ($match.Success) { return $match.Groups[1].Value.Trim().Trim('"', "'") }
    return ""
}

function Get-FrontmatterTags {
    param([string]$Content)
    $inline = [regex]::Match($Content, "(?m)^tags:\s*\[(.*?)\]")
    if ($inline.Success) {
        return ($inline.Groups[1].Value -split "," | ForEach-Object { $_.Trim().Trim('"', "'") }) -join ","
    }
    $listMatches = [regex]::Matches($Content, "(?m)^  -\s*(.+)$")
    if ($listMatches.Count -gt 0) {
        return ($listMatches | ForEach-Object { $_.Groups[1].Value.Trim().Trim('"', "'") }) -join ","
    }
    return ""
}

$Parsed = @()
foreach ($f in $Files) {
    $content = Get-Content $f.FullName -Raw
    $dateStr = Get-FrontmatterValue -Content $content -Key "date"
    $typeStr = Get-FrontmatterValue -Content $content -Key "type"
    $tagsStr = Get-FrontmatterTags -Content $content

    $keywords = ""
    switch ($typeStr) {
        "decision" {
            $matches = [regex]::Matches($content, "(?m)^## (Options Considered|Decision|Rationale|Consequences)$")
            $keywords = ($matches | ForEach-Object { $_.Groups[1].Value }) -join ","
        }
        "failure" {
            $matches = [regex]::Matches($content, "(?m)^## (What Failed|Root Cause|What We Learned|Mitigation)$")
            $keywords = ($matches | ForEach-Object { $_.Groups[1].Value }) -join ","
        }
        "entropy" {
            $matches = [regex]::Matches($content, "(?m)^## (The Smell|Prevention Rule|Detection Heuristic)$")
            $keywords = ($matches | ForEach-Object { $_.Groups[1].Value }) -join ","
            $cat = Get-FrontmatterValue -Content $content -Key "category"
            if ($cat) { $keywords = "$keywords,$cat" }
        }
        "taste" {
            $matches = [regex]::Matches($content, "(?m)^## (The Preference|Source Context|When It Applies)$")
            $keywords = ($matches | ForEach-Object { $_.Groups[1].Value }) -join ","
        }
        default {
            $matches = [regex]::Matches($content, "(?m)^##\s+(.+)$")
            $keywords = ($matches | ForEach-Object { $_.Groups[1].Value.Trim() } | Select-Object -First 5) -join ","
        }
    }

    $boldMatches = [regex]::Matches($content, "\*\*([^*]+)\*\*")
    $boldWords = ($boldMatches | ForEach-Object { $_.Groups[1].Value } | Select-Object -Unique) -join ","
    if ($boldWords) {
        if ($keywords) { $keywords = "$keywords,$boldWords" } else { $keywords = $boldWords }
    }

    $Parsed += [PSCustomObject]@{
        File = $f.Name
        Date = $dateStr
        Type = $typeStr
        Tags = $tagsStr
        Keywords = $keywords
    }
}

# Similarity matrix
$SimMatrix = @()
for ($i = 0; $i -lt $Parsed.Count; $i++) {
    for ($j = $i + 1; $j -lt $Parsed.Count; $j++) {
        $p1 = $Parsed[$i]
        $p2 = $Parsed[$j]

        $tags1 = $p1.Tags -split "," | ForEach-Object { $_.Trim() } | Where-Object { $_ } | Sort-Object -Unique
        $tags2 = $p2.Tags -split "," | ForEach-Object { $_.Trim() } | Where-Object { $_ } | Sort-Object -Unique
        $tagShared = @($tags1 | Where-Object { $_ -in $tags2 }).Count
        $tagTotal = @($tags1 + $tags2 | Sort-Object -Unique).Count

        $kws1 = $p1.Keywords -split "," | ForEach-Object { $_.Trim().ToLower() } | Where-Object { $_ } | Sort-Object -Unique
        $kws2 = $p2.Keywords -split "," | ForEach-Object { $_.Trim().ToLower() } | Where-Object { $_ } | Sort-Object -Unique
        $kwShared = @($kws1 | Where-Object { $_ -in $kws2 }).Count
        $kwTotal = @($kws1 + $kws2 | Sort-Object -Unique).Count

        $tagSim = if ($tagTotal -gt 0) { $tagShared / $tagTotal } else { 0 }
        $kwSim = if ($kwTotal -gt 0) { $kwShared / $kwTotal } else { 0 }
        $score = 0.6 * $tagSim + 0.4 * $kwSim

        if ($score -ge 0.30) {
            $sharedTags = ($tags1 | Where-Object { $_ -in $tags2 }) -join ","
            $sharedKws = ($kws1 | Where-Object { $_ -in $kws2 }) -join ","
            $SimMatrix += [PSCustomObject]@{
                F1 = $p1.File; F2 = $p2.File; Score = [math]::Round($score, 3)
                SharedTags = $sharedTags; SharedKws = $sharedKws
            }
        }
    }
}

# Union-find clustering
$ClusterMap = @{}
$NextId = 0
foreach ($p in $Parsed) {
    $ClusterMap[$p.File] = $NextId
    $NextId++
}

foreach ($sim in $SimMatrix) {
    $c1 = $ClusterMap[$sim.F1]
    $c2 = $ClusterMap[$sim.F2]
    if ($c1 -ne $c2) {
        $keys = @($ClusterMap.Keys)
        foreach ($key in $keys) {
            if ($ClusterMap[$key] -eq $c2) {
                $ClusterMap[$key] = $c1
            }
        }
    }
}

# Output clusters
Write-Host "=== Clusters Found ==="
Write-Host ""
$Groups = $ClusterMap.GetEnumerator() | Group-Object { $_.Value }
$HasCluster = $false
foreach ($g in $Groups) {
    if ($g.Count -ge 2) {
        $HasCluster = $true
        Write-Host "Cluster $($g.Name) ($($g.Count) files):"
        foreach ($item in $g.Group) {
            Write-Host "  - $($item.Key)"
        }
        Write-Host ""
    }
}
if (-not $HasCluster) {
    Write-Host "No clusters found (all files are singletons)."
    Write-Host ""
}

# Singletons
Write-Host "=== Unclustered (singletons) ==="
Write-Host ""
foreach ($g in $Groups) {
    if ($g.Count -eq 1) {
        Write-Host "  - $($g.Group[0].Key)"
    }
}
Write-Host ""

# Similarity pairs
Write-Host "=== Similarity Pairs (score >= 0.30) ==="
Write-Host ""
if ($SimMatrix.Count -gt 0) {
    foreach ($sim in ($SimMatrix | Sort-Object Score -Descending)) {
        Write-Host "$($sim.F1) <-> $($sim.F2) (score: $($sim.Score))"
        if ($sim.SharedTags) { Write-Host "  Shared tags: $($sim.SharedTags)" }
        if ($sim.SharedKws) { Write-Host "  Shared keywords: $($sim.SharedKws)" }
        Write-Host ""
    }
} else {
    Write-Host "No significant similarities found (threshold: 0.30)."
}

Remove-Item -Recurse -Force $TmpDir -ErrorAction SilentlyContinue
Write-Host "=== End of Report ==="
