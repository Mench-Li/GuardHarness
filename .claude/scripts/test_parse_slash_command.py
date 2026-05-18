import importlib.util
import json
import sys
from pathlib import Path

script_dir = Path(__file__).parent
spec = importlib.util.spec_from_file_location("parse_slash_command", script_dir / "parse-slash-command.py")
parse_slash_command = importlib.util.module_from_spec(spec)
sys.modules["parse_slash_command"] = parse_slash_command
spec.loader.exec_module(parse_slash_command)
COMMANDS = parse_slash_command.COMMANDS


def test_init_feature_has_constraint_loading():
    msg = COMMANDS["/init-feature"]
    assert "shared-axioms.md" in msg
    assert "standards.md" in msg


def test_init_feature_has_cli_prompt():
    msg = COMMANDS["/init-feature"]
    assert "agent-guard/cli.py init" in msg


def test_plan_feature_has_cli_prompt():
    msg = COMMANDS["/plan-feature"]
    assert "agent-guard/cli.py plan" in msg


def test_execute_plan_has_cli_prompt():
    msg = COMMANDS["/execute-plan"]
    assert "agent-guard/cli.py execute" in msg


def test_finish_branch_has_cli_prompt():
    msg = COMMANDS["/finish-branch"]
    assert "agent-guard/cli.py finish" in msg


def test_reflect_has_no_cli_prompt():
    msg = COMMANDS["/reflect"]
    assert "agent-guard/cli.py" not in msg
