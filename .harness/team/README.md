# Team Harness

团队级共享配置目录，用于在多项目间同步 Harness 规范、公理和 Reviewer 规则。

## 当前状态

本目录已初始化为独立 git 仓库（`.harness/team/.git/`）。
当前作为本项目内嵌的团队配置使用；如需跨项目共享，请按下方步骤注册为 git submodule。

## 作为 Submodule 使用

### 1. 创建远程仓库并推送

```bash
cd .harness/team
git remote add origin https://github.com/your-org/team-harness.git
git push -u origin master
```

### 2. 在主项目中注册为 submodule

```bash
git submodule add https://github.com/your-org/team-harness.git .harness/team
```

### 3. 更新共享配置

```bash
git submodule update --remote .harness/team
```

## Files

- `shared-axioms.md` — 团队级公理与原则（跨项目通用）
- `standards.md` — 编码、测试与文档标准
- `reviewer-pool.yaml` — Reviewer Agent 分配规则
