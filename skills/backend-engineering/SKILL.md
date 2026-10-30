---
name: backend-engineering
description: >-
  设计或审查后端、HTTP API、OpenAPI、鉴权、错误模型、数据库迁移、配置密钥、可观测性与后台任务时使用；触发词：后端工程、API 契约、接口设计、分页、幂等、权限、迁移、日志、background job、backend engineering。
---

# 后端工程

本 Skill 说明后端的**契约与运行边界应该长什么样**。怎么拆工作、实现、验证和收尾，仍用
`skill://align-work`、`skill://implement-change`、`skill://verify-work`、
`skill://review-work`、`skill://finish-work`；不要在这里另造流程。

## 何时使用

- 新增或修改 HTTP API、OpenAPI、SDK 类型、错误模型；
- 设计登录后的权限、租户隔离、对象级授权或输入边界；
- 修改持久化模型、数据库 schema、配置、密钥；
- 建设日志、指标、追踪、队列 worker 或长任务；
- 审查 Python、Rust、TypeScript 后端设计。

框架 API 会随版本变化：先查项目锁定版本的官方文档；可用 Context7 MCP 时，先
`resolve-library-id`，再 `query-docs`，不要凭记忆猜装饰器、middleware 或 migration API。
Python 临时依赖使用 `uv run --with <package> ...`，不污染项目环境。

## 场景路由

| 场景 | 先读 |
|---|---|
| 资源、路径、字段命名、分页、版本、OpenAPI、生成客户端 | [API 契约](references/api-contracts.md) |
| RFC 9457 错误、稳定错误码、幂等重试 | [API 契约](references/api-contracts.md) |
| authentication / authorization、BOLA、边界校验 | [安全边界](references/security-boundaries.md) |
| 数据建模、约束、migration、expand/contract、配置与 secrets | [数据与配置](references/data-and-config.md) |
| logs / metrics / traces、请求关联、后台任务 | [运行与后台任务](references/runtime-and-jobs.md) |
| 日志字段、异常上下文、Rust `tracing`、TS logger 示例 | [日志规范](references/logging.md) |
| UI 如何消费 API 合同 | `skill://frontend-engineering` |
| README、ADR、runbook、CHANGELOG 等文档载体 | `skill://project-docs` |

## 一个贯穿场景

要做“创建订单并异步发货”：先在 OpenAPI 定义 `POST /orders`、请求/响应、
`application/problem+json` 错误和 `Idempotency-Key` 行为；从该契约生成 TS 客户端类型。
服务端认证调用者后，再对购物车和地址做对象级授权；语法校验在入口，库存规则在业务层。
数据库先提交订单与 outbox/job 记录，再由可重试 worker 发货；日志带 trace/job ID，指标观察
吞吐、失败和延迟。若 schema 要改，按 expand → migrate → contract 让新旧版本可滚动部署。

## 最重要的规则

1. **一个机器可读契约只有一个权威来源。** OpenAPI 驱动文档、校验和客户端类型，避免手写副本漂移。
2. **把不兼容当显式设计决定。** 已发布消费者不能同步升级时才引入版本或 expand/contract；可控消费者一起迁移并收敛，遵循 `policy/working-contract.md`。
3. **认证不等于授权。** 每个携带对象标识符的操作都按“主体 × 动作 × 对象”检查，防止 BOLA。
4. **重试从第一次设计。** 有副作用的创建、回调和 job 用幂等键、唯一约束或状态机去重；同一键不同载荷应拒绝。
5. **边界先限流量再校验含义。** 先限制 body、数组和嵌套深度，再解析并校验结构与业务语义；客户端校验只改善体验。
6. **schema 与数据一起演进。** migration 版本化且小步；破坏性变化先扩展、回填/切读，再收缩。
7. **三类遥测各司其职。** metrics 看趋势，traces 串请求，logs 解释事件；共享关联上下文但不记录 secrets。
8. **后台任务默认至少一次。** worker 要能安全重跑、声明超时/重试/死信策略，并把业务状态与投递意图可靠关联。

## 自查

- [ ] 每个 operation 的成功、失败、认证、分页和幂等语义都在契约中吗？
- [ ] 客户端类型来自同一份 schema，而非复制粘贴吗？
- [ ] 另一个用户/租户拿到对象 ID 时仍无法读写吗？
- [ ] 无效、超大、未知字段输入会在进入业务逻辑前失败吗？
- [ ] migration 在混合版本部署和回滚/前滚方案下安全吗？
- [ ] 配置启动时校验，secret 不进源码、日志和普通配置样例吗？
- [ ] 任务重复、并发、超时或进程重启后，结果仍一致且可定位吗？
- [ ] 规则是否链接权威来源；框架细节是否查了当前版本官方文档？
