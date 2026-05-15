"""Agent-Guard CLI entry point.

Commands:
  init            Create a new task (Inbox)
  plan            Approve plan (Inbox -> Plan Ready)
  execute         Start execution (Plan Ready -> Executing), auto-claim if no task_id given
  claim           Claim next available task from backlog
  patch           Mark code done (Executing -> Patch Ready)
  review          Enter entropy review (Patch Ready -> Entropy Review)
  finish          Complete task (Entropy Review -> Done)
  simplify        Mark needs simplification (Entropy Review -> Needs Simplification)
  block           Mark as blocked (from any state -> Blocked)
  unblock         Resume from blocked (Blocked -> previous state)
  status          Show current task state
  list            List tasks
  resume          Resume an interrupted task from snapshot
  heartbeat       Send heartbeat for lease
  gate-check      Run a specific gate manually
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from gates import run_gate
from lease import LeaseManager
from snapshot import (
    LeaseInfo,
    PlanProgress,
    PlanStep,
    RequiredContext,
    Snapshot,
    SnapshotManager,
)
from state_machine import State, StateMachine, StateMachineError, TaskState


def _claim_next_task(holder: str | None = None) -> tuple[str, dict[str, Any]]:
    """从 backlog 中认领一个 Plan Ready 状态且没有活跃 lease 的 task。

    按 updated_at 排序，优先认领最早准备好的 task。
    如果所有 Plan Ready 的 task 都已被占用，抛出 LeaseError。
    """
    from lease import LeaseError as _LeaseError

    sm = StateMachine()
    lm = LeaseManager()

    tasks = sm.list_tasks(state_filter=State.PLAN_READY)
    tasks = sorted(tasks, key=lambda t: t.updated_at)

    for task in tasks:
        lease = lm.get_lease(task.task_id)
        if lease is None or lm.is_expired(task.task_id):
            try:
                new_lease = lm.acquire(task.task_id, holder=holder)
                return task.task_id, new_lease
            except _LeaseError:
                continue

    raise _LeaseError("No available tasks in backlog (all Plan Ready tasks have active leases)")


def _parse_plan_progress(plan_path: str) -> PlanProgress:
    """解析 plan 文件，提取 markdown 步骤列表构建 PlanProgress。"""
    import re

    content = Path(plan_path).read_text(encoding="utf-8")
    lines = content.splitlines()

    step_pattern = re.compile(r"^\s*(?:[-*]\s+|\d+\.\s+)")
    steps: list[PlanStep] = []
    for line in lines:
        if step_pattern.match(line):
            desc = re.sub(r"^\s*(?:[-*]|\d+\.)\s+", "", line).strip()
            if desc:
                steps.append(PlanStep(step=len(steps) + 1, description=desc))

    return PlanProgress(total_steps=len(steps), pending=steps)


def _fmt_task(task) -> str:
    lines = [
        f"Task: {task.task_id}",
        f"State: {task.current_state.value}",
        f"Created: {task.created_at}",
        f"Updated: {task.updated_at}",
        f"Transitions: {len(task.history)}",
    ]
    if task.history:
        last = task.history[-1]
        lines.append(f"Last transition: {last.from_state.value} -> {last.to_state.value} at {last.timestamp}")
        if last.gate_results:
            lines.append("Gate results:")
            for gate, result in last.gate_results.items():
                status = "PASS" if result.get("passed") else "FAIL"
                lines.append(f"  {gate}: {status}")
    if task.metadata:
        lines.append("Metadata:")
        for k, v in task.metadata.items():
            lines.append(f"  {k}: {v}")
    return "\n".join(lines)


def _extract_sections(content: str) -> list[tuple[str, int, int]]:
    """提取 plan 中的 top-level sections。

    返回 [(标题, 起始行号, 结束行号), ...]
    识别模式：## Heading、- [ ] **Bold**、1. Numbered item
    """
    import re

    lines = content.splitlines(keepends=True)
    section_pattern = re.compile(r"^(?:##\s+(.+)|- \[(?:x| |\-)\]\s+\*\*(.+?)\*\*|\d+\.\s+(.+))$")

    sections: list[tuple[str, int, int]] = []
    for i, line in enumerate(lines):
        m = section_pattern.match(line.strip())
        if m:
            title = (m.group(1) or m.group(2) or m.group(3)).strip()
            if title:
                sections.append((title, i, i + 1))

    # 计算每个 section 的结束行号（下一个 section 的开始或文件末尾）
    result = []
    for idx, (title, start, _) in enumerate(sections):
        end = sections[idx + 1][1] if idx + 1 < len(sections) else len(lines)
        result.append((title, start, end))
    return result


def _extract_keywords(text: str) -> set[str]:
    """从标题中提取关键词（过滤停用词和短词）。"""
    stopwords = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by",
        "implement", "create", "add", "setup", "configure", "build", "test", "集成", "实现", "创建",
        "添加", "配置", "搭建", "构建", "测试", "step", "task", "phase", "part", "section",
    }
    import re
    words = re.findall(r"[a-zA-Z]+|[一-鿿]{2,}", text.lower())
    return {w for w in words if len(w) > 2 and w not in stopwords}


def _semantic_duplicate_check(plan_path: str, sections: list[tuple[str, int, int]]) -> list[str]:
    """语义去重检测：扫描 plans/ 目录，检测是否已有语义相似的 plan。

    返回已存在 plan 的文件名列表（空列表表示无重复）。
    """
    plan_dir = Path(plan_path).parent
    new_keywords: set[str] = set()
    for title, _, _ in sections:
        new_keywords.update(_extract_keywords(title))

    duplicates: list[str] = []
    for existing in plan_dir.glob("*.md"):
        if existing.name == Path(plan_path).name:
            continue
        existing_content = existing.read_text(encoding="utf-8")
        existing_sections = _extract_sections(existing_content)
        existing_keywords: set[str] = set()
        for title, _, _ in existing_sections:
            existing_keywords.update(_extract_keywords(title))

        if not new_keywords or not existing_keywords:
            continue

        overlap = len(new_keywords & existing_keywords)
        union = len(new_keywords | existing_keywords)
        similarity = overlap / union if union else 0
        if similarity >= 0.5:
            duplicates.append(existing.name)

    return duplicates


def _slug_from_title(title: str, task_id: str) -> str:
    """从 section 标题生成有意义的子任务 ID。"""
    import re
    # 提取核心名词/技术术语
    keywords = re.findall(r"[A-Z][a-zA-Z0-9]+|[一-鿿]{2,}", title)
    if not keywords:
        keywords = re.findall(r"[a-zA-Z0-9]+", title)
    slug = "-".join(keywords[:3])  # 最多取前 3 个关键词
    if not slug:
        slug = "sub"
    # 清理特殊字符
    slug = re.sub(r"[^a-zA-Z0-9\-一-鿿]", "", slug)
    return f"{task_id}-{slug}"


def _update_parent_snapshot_with_subtasks(
    task_id: str,
    sub_tasks: list[tuple[str, str]],
    plan_path: str,
) -> None:
    """子任务拆分后，更新父任务的 snapshot，记录子任务列表和进度。"""
    if not sub_tasks:
        return

    snap_mgr = SnapshotManager()
    try:
        parent_snap = snap_mgr.load_snapshot(task_id)
    except Exception:
        # 父任务可能没有 snapshot（plan 阶段尚未生成）
        # 尝试从 state machine 获取状态创建基础 snapshot
        try:
            sm = StateMachine()
            task = sm.get_task(task_id)
            parent_snap = Snapshot(
                task_id=task_id,
                current_state=task.current_state.value,
                previous_state=task.history[-1].from_state.value if task.history else "",
                transition_time=datetime.now(timezone(timedelta(hours=8))).isoformat(),
            )
        except Exception:
            return

    parent_snap.sub_tasks = [tid for tid, _ in sub_tasks]

    # 将子 plan 文件加入 required_context.plans
    for _, spath in sub_tasks:
        if spath not in parent_snap.required_context.plans:
            parent_snap.required_context.plans.append(spath)
    # 保留主 plan
    if plan_path not in parent_snap.required_context.plans:
        parent_snap.required_context.plans.append(plan_path)

    # 用子任务作为 plan_progress 的大步骤
    parent_snap.plan_progress = PlanProgress(
        total_steps=len(sub_tasks),
        pending=[
            PlanStep(step=i + 1, description=f"子任务: {tid}")
            for i, (tid, _) in enumerate(sub_tasks)
        ],
    )

    snap_mgr._write_snapshot(parent_snap)


def _split_plan_into_subtasks(task_id: str, plan_path: str) -> list[tuple[str, str]]:
    """将 plan 文件按语义分组拆分为子 plan，并初始化子 task。

    拆分策略（优先级从高到低）：
    1. 识别 top-level sections（## Phase X、## Task X、- [ ] **Step X** 等）
    2. 语义去重：拆分前扫描 plans/ 目录，检测是否已有语义相似的 plan
    3. 如果 section 数量 >= 2，按 section 拆分，每个 section 一个子 plan
    4. 提取 section 标题关键词作为子任务名（不再强制 sub1/sub2）
    5. 如果 section 数量 < 2，回退到中点拆分
    """
    import re

    content = Path(plan_path).read_text(encoding="utf-8")
    lines = content.splitlines(keepends=True)

    sections = _extract_sections(content)

    # 防重复拆分：检查是否已存在该 task 的子 plan
    plan_dir = Path(plan_path).parent
    sm = StateMachine()
    existing_subs: list[tuple[str, str]] = []
    for existing in plan_dir.glob("*.md"):
        if existing.name == Path(plan_path).name:
            continue
        # 匹配语义拆分格式：task_id-xxx-plan.md 或 task_id-xxx-N-plan.md
        # 或中点拆分格式：stem-sub1.md、stem-sub1-N.md
        import re as _re
        m = _re.match(rf"{re.escape(task_id)}-(.+?)(?:-\d+)?-plan\.md$", existing.name)
        sub_id: str | None = None
        if m:
            sub_id = f"{task_id}-{m.group(1)}"
        else:
            m2 = _re.match(rf"{re.escape(Path(plan_path).stem)}-sub(\d+)(?:-\d+)?\.md$", existing.name)
            if m2:
                sub_id = f"{task_id}-sub{m2.group(1)}"
        if sub_id:
            try:
                sm.get_task(sub_id)
                existing_subs.append((sub_id, str(existing)))
            except StateMachineError:
                pass
    if existing_subs:
        print(f"[INFO] 该任务已拆分为 {len(existing_subs)} 个子任务，跳过重复拆分：")
        for sid, spath in existing_subs:
            print(f"  - {sid}: {spath}")
        _update_parent_snapshot_with_subtasks(task_id, existing_subs, plan_path)
        return existing_subs

    # 语义去重检测
    duplicates = _semantic_duplicate_check(plan_path, sections)
    if duplicates:
        print(f"\n[WARNING] 检测到语义重复的 plan 文件：")
        for dup in duplicates:
            print(f"  - {dup}")
        print("这些 plan 可能已经覆盖了当前 plan 的部分内容。")
        print("建议先检查现有 plan，避免重复拆分。\n")
        # 不阻断，但给出警告，让用户决定是否继续

    if len(sections) >= 2:
        # 按 section 语义分组拆分
        header_end = sections[0][1]
        footer_start = sections[-1][2]
        header = lines[:header_end]
        footer = lines[footer_start:] if footer_start <= len(lines) else []

        plan_dir = Path(plan_path).parent
        results: list[tuple[str, str]] = []

        for title, start, end in sections:
            section_lines = lines[start:end]
            sub_id = _slug_from_title(title, task_id)
            sub_path = plan_dir / f"{sub_id}-plan.md"

            # 避免覆盖已有文件
            counter = 1
            original_sub_path = sub_path
            while sub_path.exists():
                sub_path = plan_dir / f"{sub_id}-{counter}-plan.md"
                counter += 1

            sub_content = "".join(header + section_lines + footer)
            sub_path.write_text(sub_content, encoding="utf-8")

            sm = StateMachine()
            try:
                sm.init_task(sub_id, metadata={"parent": task_id, "source_plan": str(plan_path)})
            except StateMachineError:
                pass

            results.append((sub_id, str(sub_path)))

        _update_parent_snapshot_with_subtasks(task_id, results, plan_path)
        return results

    # 回退：中点拆分（旧行为）
    step_pattern = re.compile(r"^\s*(?:[-*]\s+|\d+\.\s+)")
    step_indices = [i for i, line in enumerate(lines) if step_pattern.match(line)]

    if len(step_indices) < 2:
        return []

    mid = len(step_indices) // 2
    split_idx = step_indices[mid]

    header_end = step_indices[0]
    footer_start = step_indices[-1] + 1

    header = lines[:header_end]
    footer = lines[footer_start:] if footer_start <= len(lines) else []
    part1_steps = lines[header_end:split_idx]
    part2_steps = lines[split_idx:footer_start]

    plan_dir = Path(plan_path).parent
    stem = Path(plan_path).stem

    sub1_path = plan_dir / f"{stem}-sub1.md"
    sub2_path = plan_dir / f"{stem}-sub2.md"

    counter = 1
    while sub1_path.exists() or sub2_path.exists():
        sub1_path = plan_dir / f"{stem}-sub1-{counter}.md"
        sub2_path = plan_dir / f"{stem}-sub2-{counter}.md"
        counter += 1

    sub1_path.write_text("".join(header + part1_steps + footer), encoding="utf-8")
    sub2_path.write_text("".join(header + part2_steps + footer), encoding="utf-8")

    sm = StateMachine()
    sub1_id = f"{task_id}-sub1"
    sub2_id = f"{task_id}-sub2"

    for sub_id in (sub1_id, sub2_id):
        try:
            sm.init_task(sub_id, metadata={"parent": task_id})
        except StateMachineError:
            pass

    sub_task_results = [(sub1_id, str(sub1_path)), (sub2_id, str(sub2_path))]
    _update_parent_snapshot_with_subtasks(task_id, sub_task_results, plan_path)
    return sub_task_results


def _transition_with_snapshot(
    sm: StateMachine,
    task_id: str,
    to_state: State,
    gate_results: dict[str, Any] | None = None,
    reason: str = "",
    skip_gates: bool = False,
) -> TaskState:
    """Transition task state and auto-generate snapshot for recovery."""
    task = sm.transition(task_id, to_state, gate_results=gate_results, reason=reason, skip_gates=skip_gates)

    snap_mgr = SnapshotManager()

    # Build required context from conventions
    req_ctx = RequiredContext()
    plan_candidates = [
        f"docs/superpowers/plans/{task_id}-plan.md",
        f"docs/superpowers/plans/{task_id}.md",
    ]
    for c in plan_candidates:
        if Path(c).exists():
            req_ctx.plans.append(c)
            req_ctx.files.append(c)
            break

    spec_path = task.metadata.get("spec_path")
    if spec_path and Path(spec_path).exists():
        req_ctx.files.append(spec_path)

    # 解析 plan 步骤进度：优先保留现有 snapshot 中的进度，避免覆盖
    plan_progress = None
    old_lease = None
    old_sub_tasks = None
    old_sandbox = None
    try:
        old_snapshot = snap_mgr.load_snapshot(task_id)
        plan_progress = old_snapshot.plan_progress
        old_lease = old_snapshot.lease
        old_sub_tasks = old_snapshot.sub_tasks
        old_sandbox = old_snapshot.sandbox
    except Exception:
        pass

    # 空进度也视为需要重新解析（避免首次生成 snapshot 时写入空 PlanProgress 后一直复用）
    if plan_progress is None or (plan_progress.total_steps == 0 and not plan_progress.pending):
        for c in plan_candidates:
            if Path(c).exists():
                plan_progress = _parse_plan_progress(c)
                break

    snap_mgr.create_snapshot(
        task_id,
        required_context=req_ctx,
        plan_progress=plan_progress,
        lease=old_lease,
        sub_tasks=old_sub_tasks,
        sandbox=old_sandbox,
    )
    return task


def _auto_mark_first_step_in_progress(task_id: str) -> None:
    """Execute 获得 Lease 后，自动将 plan 第 1 步标记为 in_progress。"""
    snap_mgr = SnapshotManager()
    try:
        snapshot = snap_mgr.load_snapshot(task_id)
    except Exception:
        return
    pp = snapshot.plan_progress
    if pp and pp.pending:
        first_step = pp.pending[0]
        first_step.started_at = datetime.now(timezone(timedelta(hours=8))).isoformat()
        pp.in_progress.append(first_step)
        pp.pending.pop(0)
        snap_mgr._write_snapshot(snapshot)
        print(f"Auto-marked step {first_step.step} as in_progress")


def _sync_progress_to_parent(task_id: str, snapshot) -> None:
    """将子任务的进度同步到父任务的 snapshot。"""
    sm = StateMachine()
    try:
        task = sm.get_task(task_id)
    except StateMachineError:
        return
    parent_id = task.metadata.get("parent")
    if not parent_id:
        return

    snap_mgr = SnapshotManager()
    try:
        parent_snap = snap_mgr.load_snapshot(parent_id)
    except StateMachineError:
        return

    pp = parent_snap.plan_progress
    target_step = None
    target_list = None
    for lst_name, lst in [("completed", pp.completed), ("in_progress", pp.in_progress), ("pending", pp.pending)]:
        for s in lst[:]:
            if f"子任务: {task_id}" in s.description:
                target_step = s
                target_list = lst
                break
        if target_step:
            break

    if target_step is None:
        return

    now = datetime.now(timezone(timedelta(hours=8))).isoformat()
    child_pp = snapshot.plan_progress

    # 判断子任务整体状态
    if child_pp.completed and not child_pp.in_progress and not child_pp.pending:
        # 子任务全部完成
        target_step.completed_at = now
        if target_list is not pp.completed:
            target_list.remove(target_step)
            pp.completed.append(target_step)
    elif child_pp.in_progress:
        target_step.started_at = now
        if target_list is not pp.in_progress:
            target_list.remove(target_step)
            pp.in_progress.append(target_step)
    # 否则保持当前状态

    snap_mgr._write_snapshot(parent_snap)
    print(f"Synced progress to parent {parent_id}: step {target_step.step} ({task_id}) updated")


def _sync_child_completion_to_parent(task_id: str) -> None:
    """When a child reaches Done, mark its parent step completed."""
    sm = StateMachine()
    try:
        task = sm.get_task(task_id)
    except StateMachineError:
        return
    parent_id = task.metadata.get("parent")
    if not parent_id:
        return

    snap_mgr = SnapshotManager()
    try:
        parent_snap = snap_mgr.load_snapshot(parent_id)
    except StateMachineError:
        return

    pp = parent_snap.plan_progress
    now = datetime.now(timezone(timedelta(hours=8))).isoformat()

    for lst_name, lst in [("completed", pp.completed), ("in_progress", pp.in_progress), ("pending", pp.pending)]:
        for s in lst[:]:
            if f"子任务: {task_id}" in s.description:
                s.completed_at = now
                if lst is not pp.completed:
                    lst.remove(s)
                    pp.completed.append(s)
                snap_mgr._write_snapshot(parent_snap)
                print(f"Child {task_id} done -> parent {parent_id} step {s.step} marked completed")
                return


def cmd_init(args) -> int:
    sm = StateMachine()
    meta = {}
    if args.spec:
        meta["spec_path"] = args.spec
    try:
        task = sm.init_task(args.task_id, metadata=meta)
        print(f"Created task {args.task_id} -> Inbox")
        if args.spec:
            print(f"Spec: {args.spec}")
    except StateMachineError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


def cmd_plan(args) -> int:
    sm = StateMachine()
    if not args.approve:
        print("Plan approval preview:")
        print(f"  G1 (Plan Valid): will validate plan schema and placeholders")
        print(f"  G2 (Complexity): will check file/step count budget")
        print("Use --approve to execute transition with gates.")
        return 0

    gates = {}
    g1 = run_gate("g1_plan_valid", args.task_id)
    gates["g1_plan_valid"] = g1
    if not g1["passed"]:
        print(f"G1 FAILED: {g1['message']}", file=sys.stderr)
        print(json.dumps(g1["details"], indent=2, ensure_ascii=False), file=sys.stderr)
        return 1
    print(f"G1 PASSED: {g1['message']}")

    g2 = run_gate("g2_complexity_budget", args.task_id)
    gates["g2_complexity_budget"] = g2
    if not g2["passed"]:
        print(f"G2 WARNING: {g2['message']}")
        try:
            resp = input("复杂度超出预算，是否自动拆分为多个子任务？[y/N] ")
        except EOFError:
            resp = "n"
        if resp.lower() == "y":
            plan_path = None
            candidates = [
                f"docs/superpowers/plans/{args.task_id}-plan.md",
                f"docs/superpowers/plans/{args.task_id}.md",
            ]
            for c in candidates:
                if Path(c).exists():
                    plan_path = c
                    break
            if plan_path:
                sub_tasks = _split_plan_into_subtasks(args.task_id, plan_path)
                if sub_tasks:
                    print(f"\n已拆分为 {len(sub_tasks)} 个子任务：")
                    for tid, ppath in sub_tasks:
                        print(f"  - {tid}: {ppath}")
                    print(f"\n原任务 {args.task_id} 继续审批。")
                    gates["g2_complexity_budget"] = {
                        "passed": True,
                        "message": "Complexity resolved by auto-splitting",
                        "details": {"sub_tasks": len(sub_tasks)},
                    }
                else:
                    print("自动拆分失败（步骤太少或无法识别），请手动调整计划。")
                    return 0
            else:
                print("未找到 plan 文件，无法自动拆分。")
                return 0
        else:
            return 0
    else:
        print(f"G2 PASSED: {g2['message']}")

    try:
        _transition_with_snapshot(sm, args.task_id, State.PLAN_READY, gate_results=gates, reason="Plan approved")
        print(f"Task {args.task_id} -> Plan Ready")
    except StateMachineError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


def cmd_claim(args) -> int:
    """从 backlog 中认领下一个可用的 Plan Ready 任务。"""
    try:
        task_id, lease = _claim_next_task(holder=args.holder)
    except Exception as e:
        print(f"Claim failed: {e}", file=sys.stderr)
        return 1

    if args.execute:
        sm = StateMachine()
        g3 = run_gate("g3_entropy_check", task_id)
        if not g3["passed"]:
            print(f"G3 FAILED: {g3['message']}", file=sys.stderr)
            LeaseManager().force_release(task_id)
            return 1
        print(f"G3 PASSED: {g3['message']}")
        try:
            _transition_with_snapshot(
                sm, task_id, State.EXECUTING,
                gate_results={"g3_entropy_check": g3},
                reason="Auto-claimed and started execution",
            )
            print(f"Claimed and started: {task_id} -> Executing")
        except StateMachineError as e:
            print(f"Error: {e}", file=sys.stderr)
            LeaseManager().force_release(task_id)
            return 1
    else:
        print(f"Claimed task: {task_id}")

    print(f"Lease: {lease['holder']} (expires {lease['expires_at']})")
    if not args.execute:
        print(f"Next: python .harness/agent-guard/cli.py execute {task_id}")
    return 0


def cmd_execute(args) -> int:
    sm = StateMachine()
    task_id = args.task_id
    auto_claimed = False

    if task_id is None:
        try:
            task_id, lease = _claim_next_task()
            auto_claimed = True
            print(f"Auto-claimed task: {task_id}")
        except Exception as e:
            print(f"Execute failed: {e}", file=sys.stderr)
            return 1

    g3 = run_gate("g3_entropy_check", task_id)
    if not g3["passed"]:
        print(f"G3 FAILED: {g3['message']}", file=sys.stderr)
        print(json.dumps(g3["details"], indent=2, ensure_ascii=False), file=sys.stderr)
        print(f"\nTask {task_id} cannot proceed to Executing due to entropy.")
        print(f"Options:")
        print(f"  1. Fix entropy issues and retry:  agent-guard execute {task_id}")
        print(f"  2. Send to simplification:        agent-guard simplify {task_id}")
        if auto_claimed:
            LeaseManager().force_release(task_id)
        return 1
    print(f"G3 PASSED: {g3['message']}")

    # Check if task is already in Executing state (e.g. from prior claim --execute)
    task_info = sm.get_task(task_id)
    already_executing = task_info.current_state == State.EXECUTING

    lm = LeaseManager()
    # Reuse existing lease if task is already Executing (e.g. from claim --execute),
    # otherwise acquire with the provided holder.
    existing_lease = lm.get_lease(task_id)
    if existing_lease:
        lease = existing_lease
    else:
        try:
            lease = lm.acquire(task_id, holder=args.holder)
        except Exception as e:
            print(f"Lease acquisition failed: {e}", file=sys.stderr)
            if auto_claimed:
                LeaseManager().force_release(task_id)
            return 1

    print(f"Lease acquired: {lease['holder']} (expires {lease['expires_at']})")

    if not args.no_sandbox:
        from sandbox import SandboxManager, SandboxError
        sb_mgr = SandboxManager(repo_root=".")
        try:
            info = sb_mgr.create(task_id)
            print(f"Sandbox created at {info['worktree_path']}")
            # Write sandbox info to snapshot
            try:
                from snapshot import SnapshotManager, SandboxInfo
                snap_mgr = SnapshotManager()
                snap = snap_mgr.load_snapshot(task_id)
                snap.sandbox = SandboxInfo(
                    worktree_path=info["worktree_path"],
                    branch=info["branch"],
                    created_at=info["created_at"],
                )
                snap_mgr._write_snapshot(snap)
            except Exception:
                pass
        except SandboxError as e:
            print(f"Sandbox creation failed: {e}", file=sys.stderr)
            print("Use --no-sandbox to proceed without isolation.", file=sys.stderr)
            if auto_claimed:
                LeaseManager().force_release(task_id)
            return 1

    if not already_executing:
        try:
            _transition_with_snapshot(sm, task_id, State.EXECUTING, gate_results={"g3_entropy_check": g3}, reason="Start execution")
        except StateMachineError as e:
            if "Invalid transition" in str(e) and "Executing to Executing" in str(e):
                # Task already in Executing state (e.g. from claim --execute), skip transition
                pass
            else:
                print(f"Error: {e}", file=sys.stderr)
                if auto_claimed:
                    LeaseManager().force_release(task_id)
                return 1
        print(f"Task {task_id} -> Executing")

    # 自动将 plan 第 1 步标记为 in_progress
    _auto_mark_first_step_in_progress(task_id)

    # Auto-split if plan has multiple semantic sections
    plan_path = None
    for c in [
        f"docs/superpowers/plans/{task_id}-plan.md",
        f"docs/superpowers/plans/{task_id}.md",
    ]:
        if Path(c).exists():
            plan_path = c
            break
    if plan_path:
        sub_tasks = _split_plan_into_subtasks(task_id, plan_path)
        if sub_tasks:
            print(f"\n已拆分为 {len(sub_tasks)} 个子任务：")
            for tid, ppath in sub_tasks:
                print(f"  - {tid}: {ppath}")
    return 0


def cmd_patch(args) -> int:
    sm = StateMachine()
    g4 = run_gate("g4_surgical_check", args.task_id)
    if not g4["passed"]:
        print(f"G4 FAILED: {g4['message']}", file=sys.stderr)
        print(json.dumps(g4["details"], indent=2, ensure_ascii=False), file=sys.stderr)
        return 1
    print(f"G4 {'PASSED' if g4['passed'] else 'FAILED'}: {g4['message']}")

    try:
        _transition_with_snapshot(
            sm,
            args.task_id,
            State.PATCH_READY,
            gate_results={"g4_surgical_check": g4},
            reason="Code complete",
        )
        print(f"Task {args.task_id} -> Patch Ready")
    except StateMachineError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


def cmd_review(args) -> int:
    sm = StateMachine()
    try:
        _transition_with_snapshot(sm, args.task_id, State.ENTROPY_REVIEW, reason="Begin entropy review")
        print(f"Task {args.task_id} -> Entropy Review")
    except StateMachineError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


def cmd_finish(args) -> int:
    sm = StateMachine()

    g5 = run_gate("g5_verification_proof", args.task_id)
    if not g5["passed"]:
        print(f"G5 FAILED: {g5['message']}", file=sys.stderr)
        print(json.dumps(g5["details"], indent=2, ensure_ascii=False), file=sys.stderr)
        return 1
    print(f"G5 PASSED: {g5['message']}")

    try:
        _transition_with_snapshot(
            sm,
            args.task_id,
            State.DONE,
            gate_results={"g5_verification_proof": g5},
            reason="All verifications passed",
        )
        lm = LeaseManager()
        lease = lm.get_lease(args.task_id)
        if lease:
            lm.release(args.task_id, lease["holder"])
        print(f"Task {args.task_id} -> Done")
        print("Lease released.")

        # Sync child completion to parent snapshot
        _sync_child_completion_to_parent(args.task_id)
    except StateMachineError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    # Cleanup sandbox AFTER verification and state transition
    from sandbox import SandboxManager, SandboxError
    sb_mgr = SandboxManager(repo_root=".")
    sandbox = sb_mgr.get_sandbox(args.task_id)
    if sandbox:
        try:
            patch = sb_mgr.extract_patch(args.task_id)
            print(f"Patch extracted to {patch}")
            sb_mgr.destroy(args.task_id, extract_patch_first=False)
            print(f"Sandbox destroyed for {args.task_id}")
        except SandboxError as e:
            print(f"Sandbox cleanup warning: {e}", file=sys.stderr)

    return 0


def cmd_simplify(args) -> int:
    sm = StateMachine()
    try:
        task = sm.get_task(args.task_id)
        from_state = task.current_state.value
        _transition_with_snapshot(
            sm,
            args.task_id,
            State.NEEDS_SIMPLIFICATION,
            reason=f"Entropy/surgical check failed from {from_state}",
        )
        lm = LeaseManager()
        lease = lm.get_lease(args.task_id)
        if lease:
            lm.release(args.task_id, lease["holder"])
        print(f"Task {args.task_id} -> Needs Simplification")
        print("Next steps:")
        print(f"  1. Simplify code")
        print(f"  2. Re-enter execution:  agent-guard execute {args.task_id}")
        print(f"  3. Or back to planning: agent-guard plan {args.task_id} --approve")
    except StateMachineError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


def cmd_block(args) -> int:
    sm = StateMachine()
    try:
        task = sm.get_task(args.task_id)
        from_state = task.current_state.value
        _transition_with_snapshot(
            sm,
            args.task_id,
            State.BLOCKED,
            reason=args.reason or f"Blocked from {from_state}",
        )
        lm = LeaseManager()
        lease = lm.get_lease(args.task_id)
        if lease:
            lm.release(args.task_id, lease["holder"])
        print(f"Task {args.task_id} -> Blocked")
        print(f"Previous state: {from_state}")
        print(f"To unblock: agent-guard unblock {args.task_id}")
    except StateMachineError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


def cmd_unblock(args) -> int:
    sm = StateMachine()
    try:
        task = sm.get_task(args.task_id)
        if task.current_state != State.BLOCKED:
            print(f"Error: Task {args.task_id} is not blocked (current: {task.current_state.value})", file=sys.stderr)
            return 1
        prev = task.metadata.get("blocked_from", "Inbox")
        target = State(prev) if any(s.value == prev for s in State) else State.INBOX
        _transition_with_snapshot(sm, args.task_id, target, skip_gates=True, reason=f"Unblocked, returning to {prev}")
        print(f"Task {args.task_id} -> {target.value}")
    except StateMachineError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


def cmd_status(args) -> int:
    sm = StateMachine()
    try:
        task = sm.get_task(args.task_id)
        print(_fmt_task(task))
    except StateMachineError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


def cmd_list(args) -> int:
    sm = StateMachine()
    state_filter = None
    if args.state:
        state_filter = State(args.state)

    tasks = sm.list_tasks(state_filter=state_filter)
    if args.recoverable:
        tasks = [t for t in tasks if sm.is_recoverable(t.task_id)]
    if args.no_children:
        tasks = [t for t in tasks if not t.metadata.get("parent")]

    if not tasks:
        print("No tasks found.")
        return 0

    if args.flat:
        # 平铺显示（旧行为），标注 parent
        print(f"{'Task ID':<28} {'State':<22} {'Updated':<25} {'Transitions'}")
        print("-" * 84)
        for task in tasks:
            parent = task.metadata.get("parent", "")
            extra = f" (parent: {parent})" if parent else ""
            print(f"{task.task_id + extra:<28} {task.current_state.value:<22} {task.updated_at:<25} {len(task.history)}")
        return 0

    # 构建 parent -> children 映射，默认树形显示
    children_map: dict[str, list[Any]] = {}
    top_level = []
    for task in tasks:
        parent = task.metadata.get("parent")
        if parent:
            children_map.setdefault(parent, []).append(task)
        else:
            top_level.append(task)

    print(f"{'Task ID':<28} {'State':<22} {'Updated':<25} {'Transitions'}")
    print("-" * 84)

    for task in top_level:
        print(f"{task.task_id:<28} {task.current_state.value:<22} {task.updated_at:<25} {len(task.history)}")
        for child in children_map.get(task.task_id, []):
            cid = f"  └─ {child.task_id}"
            print(f"{cid:<28} {child.current_state.value:<22} {child.updated_at:<25} {len(child.history)}")
        children_map.pop(task.task_id, None)

    # 孤儿子 task（parent 不存在或被过滤掉了）
    for parent_id, orphans in children_map.items():
        for child in orphans:
            cid = f"  └─ {child.task_id} (parent: {parent_id})"
            print(f"{cid:<28} {child.current_state.value:<22} {child.updated_at:<25} {len(child.history)}")
    return 0


def cmd_resume(args) -> int:
    sm = StateMachine()
    lm = LeaseManager()
    snap_mgr = SnapshotManager()

    can_resume, reason = lm.can_resume(args.task_id)
    if not can_resume:
        print(f"Cannot resume: {reason}", file=sys.stderr)
        return 1
    print(f"Resume check: {reason}")

    try:
        snapshot = snap_mgr.load_snapshot(args.task_id)
    except StateMachineError as e:
        print(f"Snapshot error: {e}", file=sys.stderr)
        return 1

    holder = f"agent-{uuid.uuid4().hex[:8]}"
    lease = lm.acquire(args.task_id, holder=holder)

    print(f"\n=== Recovery Context for {args.task_id} ===")
    print(f"State: {snapshot.current_state}")
    print(f"Lease: {lease['holder']} (expires {lease['expires_at']})")

    if snapshot.sandbox and snapshot.sandbox.worktree_path:
        print(f"Sandbox: {snapshot.sandbox.worktree_path}")
        print("Change to this directory before continuing.")

    print()

    context = snap_mgr.load_required_context(snapshot)
    if context["files"]:
        print("--- Files ---")
        for path, content in context["files"].items():
            status = "loaded" if content is not None else "MISSING"
            print(f"  [{status}] {path}")
    if context["memories"]:
        print("--- Memories ---")
        for path, content in context["memories"].items():
            status = "loaded" if content is not None else "MISSING"
            print(f"  [{status}] {path}")
    if context["plans"]:
        print("--- Plans ---")
        for path, content in context["plans"].items():
            status = "loaded" if content is not None else "MISSING"
            print(f"  [{status}] {path}")

    print()
    print("=== Recovery Prompt ===")
    print(snap_mgr.build_recovery_prompt(snapshot))
    print()
    print("Resume complete. Agent should continue from the current step.")
    return 0


def cmd_heartbeat(args) -> int:
    lm = LeaseManager()
    try:
        lease = lm.heartbeat(args.task_id, args.holder)
        print(f"Heartbeat OK. Lease expires at {lease['expires_at']}")
    except Exception as e:
        print(f"Heartbeat failed: {e}", file=sys.stderr)
        return 1
    return 0


def cmd_progress(args) -> int:
    """更新 snapshot 中的 plan 步骤进度。"""

    snap_mgr = SnapshotManager()
    try:
        snapshot = snap_mgr.load_snapshot(args.task_id)
    except StateMachineError as e:
        print(f"Snapshot error: {e}", file=sys.stderr)
        return 1

    pp = snapshot.plan_progress
    step_num = args.step

    # 从现有列表中查找目标步骤
    target: PlanStep | None = None
    for lst in (pp.completed, pp.in_progress, pp.pending):
        for s in lst[:]:
            if s.step == step_num:
                target = s
                lst.remove(s)
                break
        if target:
            break

    if target is None:
        target = PlanStep(step=step_num, description=args.description or f"Step {step_num}")

    now = datetime.now(timezone(timedelta(hours=8))).isoformat()
    if args.evidence:
        target.evidence = args.evidence

    if args.status == "done":
        target.completed_at = now
        pp.completed.append(target)
        pp.in_progress = [s for s in pp.in_progress if s.step != step_num]
    elif args.status == "in_progress":
        target.started_at = now
        pp.in_progress.append(target)
    elif args.status == "pending":
        pp.pending.append(target)
        pp.in_progress = [s for s in pp.in_progress if s.step != step_num]
    else:
        print(f"Unknown status: {args.status}", file=sys.stderr)
        return 1

    # 更新 total_steps（如果步骤数增加了）
    all_steps = pp.completed + pp.in_progress + pp.pending
    if all_steps:
        pp.total_steps = max(s.step for s in all_steps)

    snap_mgr.create_step_snapshot(args.task_id, pp)
    print(f"Step {step_num} -> {args.status}")
    print(
        f"Progress: {len(pp.completed)}/{pp.total_steps} completed, "
        f"{len(pp.in_progress)} in progress, {len(pp.pending)} pending"
    )

    # 如果有父任务，同步进度
    _sync_progress_to_parent(args.task_id, snapshot)

    return 0


def cmd_gate_check(args) -> int:
    result = run_gate(args.gate_name, args.task_id)
    status = "PASSED" if result["passed"] else "FAILED"
    print(f"{args.gate_name}: {status}")
    print(result["message"])
    if result.get("details"):
        print(json.dumps(result["details"], indent=2, ensure_ascii=False))
    return 0 if result["passed"] else 1


def cmd_sandbox_create(args) -> int:
    from sandbox import SandboxManager, SandboxError
    from snapshot import SandboxInfo

    mgr = SandboxManager(repo_root=".")
    try:
        info = mgr.create(args.task_id)
        print(f"Sandbox created at {info['worktree_path']}")
        print(f"Branch: {info['branch']}")

        snap_mgr = SnapshotManager()
        try:
            snap = snap_mgr.load_snapshot(args.task_id)
            snap.sandbox = SandboxInfo(
                worktree_path=info["worktree_path"],
                branch=info["branch"],
                created_at=info["created_at"],
            )
            snap_mgr._write_snapshot(snap)
        except Exception:
            pass
    except SandboxError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


def cmd_sandbox_destroy(args) -> int:
    from sandbox import SandboxManager, SandboxError

    mgr = SandboxManager(repo_root=".")
    try:
        result = mgr.destroy(args.task_id, extract_patch_first=args.patch)
        if result.get("patch_path"):
            print(f"Patch extracted to {result['patch_path']}")
        print(f"Sandbox destroyed for {args.task_id}")
    except SandboxError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


def cmd_sandbox_patch(args) -> int:
    from sandbox import SandboxManager, SandboxError

    mgr = SandboxManager(repo_root=".")
    try:
        patch = mgr.extract_patch(args.task_id)
        print(f"Patch extracted to {patch}")
    except SandboxError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


def cmd_sandbox(args) -> int:
    if args.sandbox_cmd == "create":
        return cmd_sandbox_create(args)
    if args.sandbox_cmd == "destroy":
        return cmd_sandbox_destroy(args)
    if args.sandbox_cmd == "patch":
        return cmd_sandbox_patch(args)
    print(f"Unknown sandbox command: {args.sandbox_cmd}", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent-guard", description="Agent-Guard state-driven control plane")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # init
    p_init = subparsers.add_parser("init", help="Initialize a new task (Inbox)")
    p_init.add_argument("task_id")
    p_init.add_argument("--spec", default=None, help="Path to spec file")

    # plan
    p_plan = subparsers.add_parser("plan", help="Approve plan (Inbox -> Plan Ready)")
    p_plan.add_argument("task_id")
    p_plan.add_argument("--approve", action="store_true", help="Actually execute the transition")

    # execute
    p_exec = subparsers.add_parser("execute", help="Start execution (Plan Ready -> Executing)")
    p_exec.add_argument("task_id", nargs="?", default=None, help="Task ID (omit to auto-claim from backlog)")
    p_exec.add_argument("--no-sandbox", action="store_true", help="Skip worktree sandbox creation")
    p_exec.add_argument("--holder", default=None, help="Lease holder ID (must match if already claimed)")

    # claim
    p_claim = subparsers.add_parser("claim", help="Claim next available task from backlog")
    p_claim.add_argument("--execute", action="store_true", help="Auto-transition to Executing after claim")
    p_claim.add_argument("--holder", default=None, help="Lease holder ID")

    # patch
    p_patch = subparsers.add_parser("patch", help="Mark code done (Executing -> Patch Ready)")
    p_patch.add_argument("task_id")

    # review
    p_review = subparsers.add_parser("review", help="Enter entropy review (Patch Ready -> Entropy Review)")
    p_review.add_argument("task_id")

    # finish
    p_finish = subparsers.add_parser("finish", help="Complete task (Entropy Review -> Done)")
    p_finish.add_argument("task_id")

    # progress
    p_progress = subparsers.add_parser("progress", help="Update plan step progress in snapshot")
    p_progress.add_argument("task_id")
    p_progress.add_argument("--step", type=int, required=True, help="Step number to update")
    p_progress.add_argument("--status", required=True, choices=["pending", "in_progress", "done"], help="New status")
    p_progress.add_argument("--evidence", default=None, help="Evidence / completion note")
    p_progress.add_argument("--description", default=None, help="Step description (if step not yet tracked)")

    # simplify
    p_simplify = subparsers.add_parser("simplify", help="Mark needs simplification (any -> Needs Simplification)")
    p_simplify.add_argument("task_id")

    # block
    p_block = subparsers.add_parser("block", help="Block task (any -> Blocked)")
    p_block.add_argument("task_id")
    p_block.add_argument("--reason", default=None, help="Block reason")

    # unblock
    p_unblock = subparsers.add_parser("unblock", help="Unblock task (Blocked -> previous)")
    p_unblock.add_argument("task_id")

    # status
    p_status = subparsers.add_parser("status", help="Show task status")
    p_status.add_argument("task_id")

    # list
    p_list = subparsers.add_parser("list", help="List tasks")
    p_list.add_argument("--state", default=None, help="Filter by state")
    p_list.add_argument("--recoverable", action="store_true", help="Only show recoverable tasks")
    p_list.add_argument("--flat", action="store_true", help="Flat list (show parent metadata instead of tree)")
    p_list.add_argument("--no-children", action="store_true", help="Exclude sub-tasks (tasks with a parent)")

    # resume
    p_resume = subparsers.add_parser("resume", help="Resume task from snapshot")
    p_resume.add_argument("task_id")

    # heartbeat
    p_hb = subparsers.add_parser("heartbeat", help="Send heartbeat for lease")
    p_hb.add_argument("task_id")
    p_hb.add_argument("--holder", default=None, help="Lease holder ID")

    # gate-check
    p_gate = subparsers.add_parser("gate-check", help="Run a specific gate")
    p_gate.add_argument("gate_name")
    p_gate.add_argument("task_id")

    # sandbox
    p_sandbox = subparsers.add_parser("sandbox", help="Manage task sandboxes")
    sandbox_sub = p_sandbox.add_subparsers(dest="sandbox_cmd", required=True)

    p_sb_create = sandbox_sub.add_parser("create", help="Create a worktree sandbox")
    p_sb_create.add_argument("task_id")

    p_sb_destroy = sandbox_sub.add_parser("destroy", help="Destroy a worktree sandbox")
    p_sb_destroy.add_argument("task_id")
    p_sb_destroy.add_argument("--patch", action="store_true", default=True, help="Extract patch before destruction")

    p_sb_patch = sandbox_sub.add_parser("patch", help="Extract patch from sandbox")
    p_sb_patch.add_argument("task_id")

    args = parser.parse_args(argv)

    handlers = {
        "init": cmd_init,
        "plan": cmd_plan,
        "execute": cmd_execute,
        "claim": cmd_claim,
        "patch": cmd_patch,
        "review": cmd_review,
        "finish": cmd_finish,
        "progress": cmd_progress,
        "simplify": cmd_simplify,
        "block": cmd_block,
        "unblock": cmd_unblock,
        "status": cmd_status,
        "list": cmd_list,
        "resume": cmd_resume,
        "heartbeat": cmd_heartbeat,
        "gate-check": cmd_gate_check,
        "sandbox": cmd_sandbox,
    }

    if args.command == "heartbeat" and args.holder is None:
        lm = LeaseManager()
        lease = lm.get_lease(args.task_id)
        if lease:
            args.holder = lease["holder"]
        else:
            print("No active lease found; use --holder", file=sys.stderr)
            return 1

    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
