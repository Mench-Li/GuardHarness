# Agent-Guard v2.8 优化设计

## 目标
基于 TASK-019 完成后的代码审查，对 Agent-Guard 进行 11 项精细化优化，提升鲁棒性、可观测性和开发者体验。

## 优化点 1: Archive Script 安全门
**问题**: archive-legacy-tasks.py 默认直接修改数据，无备份、无 dry-run，误操作风险高。
**设计**:
- 添加 `argparse` 命令行解析
- 默认 `--dry-run`，不实际修改任何文件
- 必须显式传入 `--apply` 才执行真实修改
- 支持 `--task TASK-018` 按前缀过滤（默认 TASK-018）
- 修改前自动备份 registry.json 到 `registry.json.backup.<timestamp>`
**测试**: dry-run 模式下不修改文件；--apply 模式下正确归档并生成备份

## 优化点 2: Claim 过滤统计
**问题**: `_claim_next_task()` 返回 None 时，开发者无法判断是全部完成还是被过滤掉。
**设计**:
- 在过滤链最后增加统计输出
- 错误信息包含：叶子节点数、来源计划匹配数、伪任务过滤数、活跃租约占用数
**测试**: 过滤后输出包含具体统计数字

## 优化点 3: Done 快照进度闭合
**问题**: `finish` 后 snapshot 中 `in_progress: 1, pending: 46` 未清零，状态仍显示 Patch Ready。
**设计**:
- `cmd_finish()` 中更新 snapshot 时，强制将 `pending` 和 `in_progress` 设为 0，`completed` 设为总任务数
- snapshot state 设为 Done
**测试**: finish 后 snapshot 所有计数器归零，state 为 Done

## 优化点 4: Sandbox 销毁标记
**问题**: finish 后 snapshot 中 worktree_path 仍指向已销毁的目录，缺少销毁记录。
**设计**:
- `cmd_finish()` 中 worktree_path 设为 None，patch_path 设为 None
- 添加 `destroyed_at` 时间戳
- 移除 `sandbox` 块中的 `worktree_path` 和 `patch_path`，或设为 null
**测试**: finish 后 snapshot 中 sandbox 字段正确清理

## 优化点 5: Gate Fail-Closed（_get_sandbox_cwd）
**问题**: `_get_sandbox_cwd()` 对非 Done 任务返回 "."，可能掩盖严重路径错误。
**设计**:
- 若 snapshot 不存在或无法解析，且任务状态不是 Done，抛出明确异常（而非回退到 "."）
- Done 任务可安全返回 "."（无 sandbox 需求）
**测试**: 非 Done 任务缺失 snapshot 时抛出异常

## 优化点 6: State-Root 锚定
**问题**: StateMachine 使用相对路径，在子目录运行可能读写错误位置。
**设计**:
- 支持 `GUARDHARNESS_ROOT` 环境变量覆盖状态根目录
- CLI 支持 `--state-root` 参数
- 默认值保持当前行为（项目根目录）
**测试**: 设置环境变量后状态文件写入指定目录

## 优化点 7: --include-archived CLI 标志
**问题**: `list_tasks()` 支持 `include_archived` 参数，但 CLI `cmd_list()` 未暴露。
**设计**:
- `cmd_list()` 添加 `--include-archived / --no-include-archived` 参数（默认 False）
- 传给 `list_tasks()`
**测试**: 默认隐藏 archived 任务，--include-archived 显示

## 优化点 8: finishing-policy.yaml 解析失败警告
**问题**: `g5_verification_proof()` 中解析失败时静默降级，开发者不知情。
**设计**:
- 解析失败时输出明确警告（stderr 或 logging）
- 降级到默认策略，但提示用户检查文件
**测试**: 损坏的 YAML 触发警告但 Gate 仍通过

## 优化点 9: 文档同步修复
**问题**: `.claude/skills/execute-plan/SKILL.md` 第 37 行错误声称 review 触发 G5（实际 finish 触发）。
**设计**:
- 将 "review triggers G5" 改为 "finish triggers G5"
**测试**: 无需测试，纯文档修正

## 优化点 10: Split 文档字符串澄清
**问题**: `_split_plan_into_subtasks()` 移除 midpoint fallback 后，docstring 未同步更新。
**设计**:
- 更新 docstring：明确说明找不到 Task 头部时返回空列表，不再回退 midpoint
**测试**: 无需测试，纯文档修正

## 优化点 11: CI Smoke Tests
**问题**: Agent-Guard 缺少快速回归测试，安装或基本命令损坏难以发现。
**设计**:
- 新增 `.github/workflows/smoke.yml`（或本地等效脚本）
- 测试命令：
  - `python install.py --list`
  - `python .harness/agent-guard/cli.py --help`
  - `python .harness/agent-guard/scripts/archive-legacy-tasks.py --help`
  - `python .harness/agent-guard/scripts/archive-legacy-tasks.py --dry-run`
**测试**: CI 本身即为测试

## 依赖
- 基于 TASK-019 已完成的 6 项 runtime hardening 任务
- 需修改文件：
  - `.harness/agent-guard/scripts/archive-legacy-tasks.py`
  - `.harness/agent-guard/cli.py`
  - `.harness/agent-guard/state_machine.py`
  - `.harness/agent-guard/gates.py`
  - `.claude/skills/execute-plan/SKILL.md`
  - `.github/workflows/smoke.yml`（新建）
