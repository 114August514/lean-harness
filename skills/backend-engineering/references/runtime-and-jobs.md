# 运行可观测性与后台任务

## 三种信号解决不同问题

OpenTelemetry 把 traces、metrics、logs 作为主要 telemetry signals：

| 信号 | 擅长回答 | 例子 |
|---|---|---|
| metrics | 是否普遍变慢/变坏，趋势多大 | request rate、error rate、latency histogram、queue depth |
| traces | 单次请求经过了哪里、耗时在哪 | HTTP → service → DB → queue |
| logs | 某个离散事件发生了什么 | job failed、authorization denied |

不要用无限增长的 `user_id`、URL 原始 path、error message 做 metric label；高基数会让成本和查询失控。
HTTP span 使用路由模板而非具体 ID。logs 与 spans 带 trace/span ID 才能从聚合异常下钻到单次事件。
字段与语言示例见 [日志规范](logging.md)。

最小起点：

- HTTP：按 route/method/status 的请求数、错误数、延迟；
- dependency：调用数、失败、延迟；
- job：入队、开始、成功、失败、重试、耗时、queue age/depth；
- 业务关键结果：例如订单创建成功/失败，但避免把业务实体 ID 做 label。

健康检查区分“进程是否活着”和“是否能接流量”；不要让存活检查依赖暂时故障的下游，否则编排器会
制造重启风暴。就绪检查只覆盖接流量的必要依赖。

## 结构化日志

事件名保持稳定，把变化值放字段；错误日志保留 cause/stack（仅内部）和关联 ID。不要同时在每层记录
同一异常，通常由拥有处理决定的边界记录一次。敏感字段、完整请求/响应和用户内容默认不记录。

```rust
tracing::error!(job_id = %job_id, attempt, error = ?err, "job execution failed");
```

```ts
logger.error({ err, jobId, attempt }, "job execution failed");
```

```python
logger.error(
    "job execution failed", extra={"job_id": job_id, "attempt": attempt}, exc_info=True
)
```

生产代码使用项目已有的 structured logger / telemetry SDK；框架 instrumentation 和语义约定随版本
变化，查官方文档或 Context7。

## 何时改为后台任务

当操作超过交互请求的可接受时限、需要独立重试/削峰，或第三方调用不应占住数据库事务时，使用队列或
持久 job。不要只 `spawn`/`create_task` 后立即返回：进程退出、部署或崩溃时内存任务会丢。

对 HTTP 长操作，Microsoft REST 指南采用 `202 Accepted` + 可轮询 status monitor 的模式。通用设计：

```http
POST /exports
202 Accepted
Location: /operations/op_123

GET /operations/op_123
{"status":"running","progress":42}
```

定义终态、失败 Problem Details、结果位置、取消语义与 status resource 的保留期。

## 至少一次交付下的正确性

常见 broker/worker 更容易提供 at-least-once；因此任务处理器默认会重复、并发、乱序：

1. 业务唯一键或 event ID 建唯一约束；先声明“同一次工作”如何识别。
2. handler 重入时读取持久状态；已完成则返回既有结果，不重复副作用。
3. 状态迁移用条件更新/乐观锁，避免两个 worker 同时通过“先读后写”。
4. 设 timeout、最大 attempts 和指数退避；只重试暂时性错误，永久输入错误直接终止。
5. 达到上限进入 dead-letter/failed 状态，保留可诊断原因和人工恢复入口。
6. 对事件顺序有要求时，用版本号/状态机拒绝倒退，不能信到达顺序。

“exactly once”口号不能消除外部副作用；发邮件、扣款等仍需要对方幂等键或本地去重记录。

## 数据提交与入队的一致性

以下顺序都有窗口：先提交订单再发队列，进程可能在两者之间崩溃；先发队列，消费者可能读不到尚未提交
的数据。可用 transactional outbox：同一数据库事务写业务状态和 outbox 行，独立 relay 重试发布；
consumer 仍需去重。若基础设施原生支持事务消息，先查其精确保证，不凭名称推断。

定时任务也可能重叠：让任务本身幂等，并按业务需要用 lease/单例调度或分区所有权。lease 过期后旧
worker 仍可能继续执行，因此 fencing token/条件写比“拿到锁就绝对安全”更可靠。

## 运行检查问题

- API 返回 202 后，客户端能否可靠查到成功、失败和结果？
- 同一消息同时送达两次、worker 在副作用后崩溃、任务乱序时会怎样？
- retry 是否只覆盖暂时错误，并有 timeout、上限、退避和死信？
- dashboard/alert 能否从指标定位到 trace，再到不泄密的日志？
- queue age、失败率与 dead-letter 增长是否可见？

## 来源

- https://opentelemetry.io/docs/concepts/observability-primer/
- https://opentelemetry.io/docs/concepts/signals/
- https://opentelemetry.io/docs/specs/otel/logs/data-model/
- https://github.com/microsoft/api-guidelines/blob/vNext/azure/Guidelines.md#long-running-operations--jobs
- https://docs.stripe.com/api/idempotent_requests
