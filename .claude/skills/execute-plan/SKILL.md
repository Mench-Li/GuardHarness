---
name: execute-plan
description: 执行实现计划（加载 executing-plans 或 subagent-driven-development skill）
---

# execute-plan

## Usage

```
/execute-plan <plan-path>
```

## Workflow

1. 读取用户提供的 `plan-path` 文件，评估任务复杂度
2. **Agent-Guard 状态转换（必须先做）**
   - 从 plan 文件或用户输入中提取 `task_id`
   - 运行 `python .harness/agent-guard/cli.py execute <task-id>`
   - 执行 G3 Entropy Check，转换状态 Plan Ready → Executing，获取 Lease
   - 如果状态转换失败（G3 阻断、状态不对等），立即停止并报告用户
3. 根据复杂度选择技能：
   - 任务多且独立 → 使用 Skill 工具加载 `subagent-driven-development` skill
   - 任务少或需要频繁确认 → 使用 Skill 工具加载 `executing-plans` skill
4. 严格按照计划逐步执行
5. 每个任务完成后运行测试并提交代码
6. **更新 Agent-Guard 进度**：`python .harness/agent-guard/cli.py progress TASK-xxx --step N --status done --evidence "commit SHA"`
7. 测试失败立即停止并报告
8. 确认 diff 只修改了计划中的文件，无 drive-by refactoring
9. **状态转换：patch（必须）**
   - 所有任务完成后，运行 `python .harness/agent-guard/cli.py patch TASK-xxx`
   - 触发 G4 Surgical Check（diff 范围审查），转换 Executing → Patch Ready
   - 如果 G4 失败（修改了计划外文件），停止并回滚无关修改后重试
   - **不要跳过此步骤。** Snapshot 不会自动进入 Patch Ready。
10. **状态转换：review（必须）**
    - 所有任务完成后，运行 `python .harness/agent-guard/cli.py review TASK-001`
    - 触发 Entropy Review，转换 Patch Ready → Entropy Review
    - 如果 review 失败（熵过高），停止并简化后重试
    - **不要跳过此步骤。** Snapshot 不会自动进入 Entropy Review。
11. **状态转换：finish（必须）**
    - 所有任务完成后，运行 `python .harness/agent-guard/cli.py finish TASK-xxx`
    - 触发 G5 Verification Proof（运行验证命令并确认通过），转换 Entropy Review → Done
    - 如果 finish 失败，修复问题后重新运行 `finish`
    - **不要跳过此步骤。**