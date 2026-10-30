# 日志：可检索、可关联、不泄密

日志记录离散事件；metrics 看聚合趋势，traces 串起一次请求。三者的分工和最小埋点见
[运行与后台任务](runtime-and-jobs.md)，API 对外错误见
[API 契约](api-contracts.md#错误模型)。

## 事件与字段

事件正文稳定、简短，把变化值放结构化字段，便于聚合和查询：

```text
差："user 42 failed order 981 because timeout"
好：message="order submission failed"
    user_id="42" order_id="981" error_kind="upstream_timeout"
```

OpenTelemetry Logs Data Model 把一条 log record 建模为 timestamp、severity、body、attributes，
并可携带 trace/span ID。项目应统一字段名和类型，例如：

| 字段 | 用途 |
|---|---|
| `service.name`, `deployment.environment.name` | 来源与环境 |
| `trace_id`, `span_id`, `request_id` | 跨信号/请求关联 |
| `event.name` | 稳定事件分类 |
| `error.type` | 可聚合的错误类别 |
| `job_id`, `attempt` | 后台任务定位 |

不要把原始 URL（含 ID）、用户 ID 或自由文本放进 metric label；日志字段可容纳这些诊断值，但仍受
隐私、保留期和访问控制约束。

## 级别与记录位置

项目统一语义即可，不要把每个分支都升级成告警：

- `DEBUG/TRACE`：开发或临时诊断细节；生产默认可关闭。
- `INFO`：低频、重要且正常的状态变化或业务结果。
- `WARN`：当前操作仍可完成，但出现降级、临近限制或需要关注的异常。
- `ERROR`：当前操作失败，或系统进入需要处理的状态。

错误在**拥有处理决定的边界**记录一次。底层保留/包装 cause，上层决定重试、转换还是终止；每层都打
同一 stack 会制造噪声。健康检查、轮询和高频成功请求应采样或用 metrics，而不是逐条 INFO。

## 三种语言的结构化示意

具体调用签名以项目锁定版本文档为准；下面只展示“静态事件 + 字段 + cause”：

```rust
tracing::error!(
    order_id = %order_id,
    error = ?err,
    "order submission failed"
);
```

```ts
logger.error(
  { err, orderId, traceId },
  "order submission failed",
);
```

```python
logger.error(
    "order submission failed",
    extra={"order_id": order_id, "trace_id": trace_id},
    exc_info=True,
)
```

不要用字符串插值吞掉结构，也不要为了统一格式手写 logger；复用项目已有 logging / tracing SDK。

## 敏感信息与不可信输入

默认不记录：

- password、session、cookie、API key、Authorization header、私钥；
- 完整请求/响应 body、支付信息、身份证件和用户上传原文；
- 数据库连接串、SQL 参数、内部 stack（对外响应中）。

只记录排障真正需要的最小元数据；必要时使用不可逆摘要或内部 opaque ID，而不是“遮住中间几位”就
假定安全。OWASP 输入校验指南还提醒：拒绝的原始输入可能含 secret 或日志注入字符，不要原样记录；
若确需保留，先按日志格式安全编码并设长度上限。

API Problem Details 的 `detail` 面向消费者，内部日志面向维护者，二者不要共用同一字符串。RFC 9457
明确提醒 problem details 不应暴露实现内部信息。对外给稳定 `type`/`code` 和 occurrence ID；内部用
该 ID 关联 cause 与 stack。

## 授权与审计事件

授权拒绝日志至少能回答：哪个主体、什么动作、哪类对象、决策、关联 ID；避免记录 token 或对象内容。
安全审计日志与普通运行日志目的不同：前者可能要求更长保留、更强访问控制和防篡改。是否构成审计事件
由威胁模型/合规要求决定，不要把全部 INFO 日志误当审计轨迹。

```text
event.name="authorization.denied"
principal_id="usr_..." action="project.read"
resource_type="project" resource_id="prj_..."
decision="deny" trace_id="..."
```

对象级授权规则见 [安全边界](security-boundaries.md#对象级授权与-bola)。

## 自查

- [ ] 事件正文是否稳定，变化值是否在字段中？
- [ ] 同一请求/job 能否通过 trace/request/job ID 串起来？
- [ ] 同一错误是否只在负责处理的边界记录一次并保留 cause？
- [ ] 是否避免 secret、完整 body、用户原文和无界字段？
- [ ] 高频信息是否用 metrics、采样或更低级别，而非刷屏？
- [ ] 对外 Problem Details 是否与内部诊断分离？

## 来源

- https://opentelemetry.io/docs/specs/otel/logs/data-model/
- https://opentelemetry.io/docs/concepts/observability-primer/
- https://www.rfc-editor.org/rfc/rfc9457.html
- https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html
- https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html
