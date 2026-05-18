#!/usr/bin/env bash
# GuardHarness 一行命令安装脚本（Bash / Git Bash / WSL / macOS / Linux）
#
# 用法:
#   cd /path/to/your-project
#   curl -fsSL https://raw.githubusercontent.com/Mench-Li/GuardHarness/main/install.sh | bash
#
# 选项:
#   curl ... | bash -s -- -y        # 自动确认覆盖
#   curl ... | bash -s -- -t ./my-project   # 安装到指定目录

set -e

GITHUB_REPO="https://github.com/Mench-Li/GuardHarness"

# 检测 Python
PYTHON=""
if command -v python3 &>/dev/null; then
    PYTHON="python3"
elif command -v python &>/dev/null; then
    PYTHON="python"
else
    echo "[ERR]  需要 Python 3.10+，请先安装 Python: https://python.org"
    exit 1
fi

# 获取版本
PY_VERSION=$($PYTHON -c "import sys; print(sys.version_info.major, sys.version_info.minor)" 2>/dev/null || echo "0 0")
PY_MAJOR=$(echo "$PY_VERSION" | awk '{print $1}')
PY_MINOR=$(echo "$PY_VERSION" | awk '{print $2}')

if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]); then
    echo "[ERR]  需要 Python 3.10+，当前版本: $PY_MAJOR.$PY_MINOR"
    exit 1
fi

echo "[INFO] 使用 Python: $($PYTHON --version)"

# 检测 Git
if ! command -v git &>/dev/null; then
    echo "[ERR]  需要 Git，请先安装 Git: https://git-scm.com"
    exit 1
fi

# 克隆仓库到临时目录
TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

echo "[INFO] 从远程仓库克隆 Harness 模板..."
git clone --depth 1 "$GITHUB_REPO" "$TMP_DIR/harness"

# 将额外参数传给 install.py
echo "[INFO] 开始安装..."
$PYTHON "$TMP_DIR/harness/install.py" "$@"
