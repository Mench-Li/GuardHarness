# Parse slash commands from user input and inject systemMessage.
# Hook into Claude Code's user_prompt_submit to intercept commands like
# /init-feature, /plan-feature, etc.
#
# Usage in .claude/settings.json:
#   "hooks": {
#     "user_prompt_submit": [
#       ".claude/scripts/parse-slash-command.ps1"
#     ]
#   }

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonScript = Join-Path $scriptDir "parse-slash-command.py"

# Ensure python is available; fallback to python3 then py
$pythonExe = $null
foreach ($cmd in @("python", "python3", "py")) {
    if (Get-Command $cmd -ErrorAction SilentlyContinue) {
        $pythonExe = $cmd
        break
    }
}

if (-not $pythonExe) {
    Write-Output "{}"
    exit 0
}

# Run the Python script, passing stdin through
& $pythonExe $pythonScript
