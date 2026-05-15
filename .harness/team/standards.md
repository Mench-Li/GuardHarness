# Team Standards

## 目录结构
```
src/
  ├── api/          # 路由和控制器
  ├── services/     # 业务逻辑
  ├── models/       # 数据模型
  ├── core/         # 配置和基础设施
  └── tests/        # 测试文件（与源码镜像结构）
```

## 提交规范
- 使用 Conventional Commits
- 每个 commit 对应一个 plan 中的 task
- 提交前必须运行 `pytest` 和 `ruff check`

## 文档标准
- 所有模块必须包含 `__init__.py` 说明
- 复杂函数包含简短 docstring（不超过 2 行）
- 架构决策记录存放于 `docs/adr/`
