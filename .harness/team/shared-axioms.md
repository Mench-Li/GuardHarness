# Team Axioms

## API Design
- RESTful API 必须使用 HTTP 状态码表示结果
- 所有外部接口必须带版本号前缀 /v1/

## Testing
- 所有外部依赖必须 Mock（单元测试）
- 集成测试必须命中真实数据库
- 覆盖率阈值：80%

## Python
- 使用 Pydantic v2 进行数据验证
- 异步优先：数据库和网络 IO 必须使用 async
- 类型注解覆盖率 100%

## AI Workflow
- 设计阶段至少 1 轮 Evaluator 审查
- 计划中禁止 TODO 和占位符
- TDD 强制：无失败测试不写生产代码
