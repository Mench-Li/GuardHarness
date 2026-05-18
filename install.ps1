# GuardHarness 一行命令安装脚本（Windows PowerShell）
#
# 用法:
#   cd C:\path\to\your-project
#   irm https://raw.githubusercontent.com/Mench-Li/GuardHarness/main/install.ps1 | iex
#
# 选项:
#   $env:HARNESS_YES="1"; irm ... | iex      # 自动确认覆盖

$ErrorActionPreference = "Stop"

$GithubRepo = "https://github.com/Mench-Li/GuardHarness"

# 检测 Python
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    $python = Get-Command python3 -ErrorAction SilentlyContinue
}
if (-not $python) {
    Write-Host "[ERR]  需要 Python 3.10+，请先安装 Python: https://python.org" -ForegroundColor Red
    exit 1
}

# 检查版本
$versionStr = & $python.Source -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
if (-not $versionStr) {
    Write-Host "[ERR]  无法获取 Python 版本" -ForegroundColor Red
    exit 1
}

$parts = $versionStr.Split(".")
$major = [int]$parts[0]
$minor = [int]$parts[1]

if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 10)) {
    Write-Host "[ERR]  需要 Python 3.10+，当前版本: $versionStr" -ForegroundColor Red
    exit 1
}

Write-Host "[INFO] 使用 Python: $(& $python.Source --version)"

# 临时目录
$tmpDir = Join-Path $env:TEMP "harness-install-$(Get-Random)"
New-Item -ItemType Directory -Path $tmpDir -Force | Out-Null

# 尝试 git clone，回退到 zip 下载
try {
    $git = Get-Command git -ErrorAction SilentlyContinue
    if ($git) {
        Write-Host "[INFO] 从远程仓库克隆 Harness 模板..."
        & $git.Source clone --depth 1 $GithubRepo "$tmpDir\harness" | Out-Host
    } else {
        Write-Host "[INFO] 未检测到 Git，尝试下载 ZIP..."
        $zipUrl = "$GithubRepo/archive/refs/heads/main.zip"
        $zipFile = "$tmpDir\harness.zip"
        Invoke-WebRequest -Uri $zipUrl -OutFile $zipFile
        Expand-Archive -Path $zipFile -DestinationPath $tmpDir -Force
        # 重命名解压后的目录为 harness
        $extracted = Get-ChildItem -Path $tmpDir -Directory | Where-Object { $_.Name -like "guardharness-*" } | Select-Object -First 1
        if ($extracted) {
            Rename-Item -Path $extracted.FullName -NewName "harness"
        }
    }

    # 组装参数
    $installArgs = @()
    if ($env:HARNESS_YES -eq "1") {
        $installArgs += "--yes"
    }
    if ($env:HARNESS_TARGET) {
        $installArgs += "--target"
        $installArgs += $env:HARNESS_TARGET
    }

    Write-Host "[INFO] 开始安装..."
    & $python.Source "$tmpDir\harness\install.py" @installArgs
} finally {
    Remove-Item $tmpDir -Recurse -Force -ErrorAction SilentlyContinue
}
