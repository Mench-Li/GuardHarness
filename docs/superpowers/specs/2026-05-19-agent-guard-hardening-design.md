# Agent-Guard 缺陷修复与一致性诊断增强设计

## 1. 范围与目标

### 1.1 必须修复的 8 项缺陷

| # | 缺陷 | 影响位置 |
|---|------|----------|
| 1 | `_get_sandbox_cwd()` 在 `--no-sandbox` 或非 Done 任务无 sandbox 时抛 `RuntimeError`，导致 G4/G5 输出 traceback 而非结构化失败。 | `gates.py:208`, `test_e2e.py:475` |
| 2 | `snapshot` 文件名仅靠微秒时间戳，Windows 下快速连续写入仍碰撞，导致 `test_step_snapshot_unique_timestamps` 偶发失败。 | `snapshot.py:196` |
| 3 | `.claude/skills/execute-plan/SKILL.md:35` 错误标注 review 触发 G5，实际应为 finish。 | `SKILL.md:35` |
| 4 | `parse-slash-command.py` 使用固定 `TASK-001`，且 `/execute-plan` 的提示与 Gate 先执行的设计冲突。 | `parse-slash-command.py:36` |
| 5 | G5 `proof_of_work` 仅配置声明（ci_status/coverage/complexity）但无可执行命令，被 `gates.py` 跳过。 | `finishing-policy.yaml:36`, `gates.py:453` |
| 6 | CI smoke test 中 `python install.py --list || true` 吞掉失败，失去阻断意义。 | `smoke.yml:12` |
| 7 | `README.md:79` 声称所有 Gate 硬阻断，但 G2 明确为警告模式（`False`）。 | `README.md:79`, `state_machine.py:67` |
| 8 | `registry.json` 中归档伪任务状态仍为 `Inbox`，与 task 文件 `Done` 不一致。 | `registry.json:114` |

### 1.2 新增能力

- `python .harness/agent-guard/cli.py doctor [TASK-xxx] [--fix]` — 一致性诊断命令，覆盖 registry/task/snapshot/lease 状态校验，长期防止类似不一致累积。

### 1.3 成功标准

- `pytest .harness/agent-guard/ -q` 结果为 `104 passed, 0 failed`（含新增 doctor 测试）。
- CLI 在任何 Gate 失败时输出结构化 JSON 而非 traceback。
- `doctor` 命令能检测并报告已知不一致模式。

---

## 2. 核心修复设计

### 2.1 `_get_sandbox_cwd` 的 fail-closed 策略

**现状：** 对非 Done 任务，若 snapshot 缺失或 worktree 无效，直接抛 `RuntimeError`，导致 CLI traceback。

**修复：**
- 在 snapshot 中显式记录 `no_sandbox: true` 标志（当任务以 `--no-sandbox` 启动时写入）。
- `_get_sandbox_cwd` 的决策逻辑改为：
  1. 若 snapshot 存在且 `no_sandbox: true`，返回当前工作目录（`os.getcwd()`）。
  2. 若 snapshot 存在且包含有效 `sandbox.worktree_path`，返回该路径。
  3. 若任务状态为 `Done`，允许回退到当前目录（归档后无 sandbox 是正常的）。
  4. 其他情况（非 Done、无 snapshot、无 worktree、非 no_sandbox）**才**抛异常，但异常由 `run_gate()` 捕获并结构化返回。

### 2.2 Snapshot 时间戳防碰撞

**现状：** `snapshot.py:196` 使用 `strftime("%Y%m%d-%H%M%S-%f")`，Windows 下 `datetime.now()` 的微秒精度在快速调用时可能重复。

**修复：**
- 时间戳文件名格式改为 `{task_id}-{timestamp}-{seq:03d}.yaml`，其中 `seq` 为同一秒内单调递增的序列号。
- 序列号通过扫描 `snapshots/` 目录下已有文件的最大序列号 +1 获得，不依赖时间精度。
- `latest` 软链接/副本逻辑保持不变。

### 2.3 `run_gate()` 统一异常捕获

**现状：** `run_gate()` 直接调用 `GATE_REGISTRY[gate_name](task_id, **kwargs)`，Gate 函数内部抛异常会导致 CLI 输出 traceback。

**修复：**
- `run_gate()` 增加 `try/except Exception` 包裹：
  ```python
  try:
      result = GATE_REGISTRY[gate_name](task_id, **kwargs)
  except Exception as exc:
      return {
          "gate": gate_name,
          "passed": False,
          "message": f"Gate execution failed: {exc}",
          "details": {"traceback": traceback.format_exc()},
          "blocking": GATE_BLOCKING.get(gate_name, True),
      }
  ```
- 确保无论 Gate 内部出现任何异常，CLI 都返回结构化的 `{"passed": false, ...}`，且 exit code 非 0。

---

## 3. 文档、配置、CI 与 Registry 修复

### 3.1 文档修正

- **SKILL.md (`.claude/skills/execute-plan/SKILL.md:35`)**：将 "review 触发 G5" 改为 "finish 触发 G5"，并修正状态转换描述为 `Entropy Review -> Done`。
- **README (`README.md:79`)**：在"每个状态转换都有硬 Gate 把关"后增加括号说明：`（G2 Complexity Budget 为警告模式，不物理阻断）`。
- **parse-slash-command (`parse-slash-command.py`)**：
  - 移除固定 `TASK-001`，改为从 slash 命令参数中动态提取任务 ID（例如 `/execute-plan docs/superpowers/plans/TASK-020.md` -> 推断 `TASK-020`）。
  - 修正 `/execute-plan` 的提示文本：将"完成后再 execute"改为"执行前先运行 `python .harness/agent-guard/cli.py execute TASK-xxx` 做 G3 Entropy Check"。

### 3.2 G5 `proof_of_work` 强化

**现状：** `finishing-policy.yaml:36-42` 只有 `type/threshold/max_cyclomatic` 声明，无可执行命令，被 `gates.py:457-458` 跳过。

**修复：**
- 为每个 `proof_of_work` 项补充可执行命令：
  - `ci_status` -> 检查环境变量 `CI` 或 `GITHUB_ACTIONS` 是否存在，若存在则读取 `GITHUB_RUN_ID` 确认 CI 运行状态。
  - `test_coverage` -> 执行 `pytest --cov=.harness/agent-guard --cov-report=term-missing`，解析输出中的覆盖率百分比，与 `threshold: 80` 比较。
  - `complexity_analysis` -> 执行 `radon cc .harness/agent-guard/ -a -nc`，解析平均复杂度，与 `max_cyclomatic: 10` 比较。
- 若相关工具（如 `pytest-cov`、`radon`）未安装，`doctor` 命令应提前检测并提示安装。

### 3.3 CI Smoke Test 强化

- 去掉 `smoke.yml:13` 的 `|| true`，使 `python install.py --list` 失败时阻断 CI。
- 新增 `windows-latest` job（项目主打 Windows 体验，当前仅测试 Ubuntu）。

### 3.4 Registry 状态同步

**现状：** `archive-legacy-tasks.py` 归档伪任务时只写入了 `archived: true`，未同步更新 `registry.json` 中的 `state`。

**修复：**
- 在归档脚本中，将伪任务的 `state` 从 `Inbox` 更新为 `Done`。
- 新增 `doctor` 命令后，可定期运行 `doctor --fix` 自动修复此类不一致（见第 4 节）。

---

## 4. Doctor 一致性检查命令

### 4.1 命令接口

```bash
python .harness/agent-guard/cli.py doctor [TASK-xxx] [--fix]
```

- 无参数：扫描全部任务，输出不一致汇总。
- `TASK-xxx`：仅检查指定任务。
- `--fix`：自动修复可安全修复的问题（如 registry state 与 task 文件不一致）。

### 4.2 检查项

| 检查名 | 说明 | 严重级别 | 是否可 --fix |
|--------|------|----------|--------------|
| `archived_state_mismatch` | registry 中 `archived=true` 但 `state != Done` | error | 是（改为 Done） |
| `task_file_registry_divergence` | task 文件存在但 registry 无记录，或反之 | error | 否（需人工确认） |
| `snapshot_sandbox_stale` | snapshot 记录的 sandbox 路径不存在且任务非 Done | warning | 否 |
| `lease_orphan` | lease 文件存在但对应任务已 Done/Archived | warning | 是（删除 lease） |
| `parent_children_state_sync` | 父任务 state 与子任务完成度不匹配（如子任务全 Done 但父任务仍在 Executing） | warning | 是（推进父任务状态） |
| `missing_proof_of_work_tool` | `finishing-policy.yaml` 要求的工具（pytest-cov、radon）未安装 | warning | 否（提示安装命令） |

### 4.3 输出格式

默认输出结构化表格（文本），便于人工阅读：
```
[TASK-018-Step-Commit] archived_state_mismatch  ERROR  registry=Inbox, task_file=Done  [FIXED]
[TASK-PARENT-ARCHIVE]  snapshot_sandbox_stale   WARN   sandbox=.worktrees/TASK-PARENT-ARCHIVE (not found)
```

JSON 模式（供脚本/CI 使用）：
```bash
python .harness/agent-guard/cli.py doctor --json
# -> {"checks": [...], "summary": {"error": 2, "warning": 3, "fixed": 1}}
```

### 4.4 与现有命令的集成

- `doctor` 不修改状态机，只读 + 可选 `--fix`。
- 建议在 `.github/workflows/smoke.yml` 中增加一步 `python .harness/agent-guard/cli.py doctor --json`，用于 CI 阶段检测数据不一致。
- `archive-legacy-tasks.py` 执行归档后，自动调用 `doctor TASK-xxx --fix` 清理该任务的 lease 和 registry 残余。

---

## 5. 测试策略

### 5.1 回归测试（现有失败修复）

| 缺陷 | 对应测试 | 验证方式 |
|------|----------|----------|
| `_get_sandbox_cwd` no-sandbox 抛异常 | `test_g4_blocks_off_plan_files` | 在 `--no-sandbox` 模式下执行 G4，断言返回 `passed: false` 而非 traceback |
| `_get_sandbox_cwd` 父任务归档抛异常 | `test_parent_done_archives_incomplete_children` 等 4 个 E2E | 父任务 finish 时 G5 能正常获取 cwd（Done 任务允许回退） |
| snapshot 时间戳碰撞 | `test_step_snapshot_unique_timestamps` | 快速写入 3 次断言产生 3 个独立文件 |
| run_gate 异常捕获 | 新增 `test_run_gate_exception_returns_structured_failure` | mock Gate 函数抛异常，断言返回 JSON 含 `passed: False` |

### 5.2 新增测试

- **`test_doctor_detects_archived_state_mismatch`**：构造 registry state=Inbox + task file Done，断言 doctor 报告 error。
- **`test_doctor_fix_updates_registry_state`**：同上，加 `--fix`，断言 registry 被改写为 Done。
- **`test_doctor_detects_lease_orphan`**：构造 Done 任务残留 lease 文件，断言 doctor 报告 warning 且 `--fix` 后 lease 被删除。
- **`test_doctor_detects_missing_proof_of_work_tool`**：在未安装 pytest-cov 的环境中运行，断言 doctor 提示安装命令。
- **`test_g5_runs_coverage_and_complexity_commands`**：构造 finishing-policy.yaml 含 coverage/complexity 命令，断言 G5 实际执行并解析输出。

### 5.3 平台覆盖

- CI 新增 `windows-latest` job，确保 snapshot 时间戳、路径处理（`\` vs `/`）在 Windows 下通过。
- 所有 doctor 测试使用临时目录隔离，不依赖真实 `registry.json`。

**目标：** `pytest .harness/agent-guard/ -q` 达到 `104 passed, 0 failed`。

---

## 6. 风险与回滚

| 风险 | 缓解措施 |
|------|----------|
| `_get_sandbox_cwd` 回退逻辑改变影响正常 worktree 任务 | 回退逻辑仅当 `no_sandbox=true` 或 `state=Done` 时触发，正常 worktree 路径优先级更高 |
| snapshot 序列号格式改变导致旧文件读取失败 | 旧文件保留，序列号仅影响新写入；`load_snapshot` 通过 glob 匹配，兼容新旧命名 |
| doctor `--fix` 误改 registry | `--fix` 仅对明确安全的项（archived_state_mismatch、lease_orphan）生效，task_file_registry_divergence 等需人工处理 |
| G5 新增命令导致 finish 变慢 | coverage/complexity 命令设 300s timeout，超时不阻断但记录 warning |
