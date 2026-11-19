# API 契约：资源、错误与重试

## 目录

- [先确定唯一契约](#先确定唯一契约)
- [资源与命名](#资源与命名)
- [分页与版本](#分页与版本)
- [错误模型](#错误模型)
- [幂等](#幂等)
- [短例子](#短例子)

## 先确定唯一契约

把 OpenAPI Description 作为 HTTP 接口的权威来源，至少描述 operation、参数、请求体、成功与失败
响应、认证方式和 schema。OpenAPI 是语言无关的 HTTP API 描述；官方说明它可供文档、客户端/
服务端代码、校验和 mock 工具消费。

推荐闭环：

```text
openapi.yaml
  ├─ lint / compatibility diff
  ├─ generated TypeScript/Python/Rust client types
  ├─ mock / human docs
  └─ server contract checks
```

- 生成文件注明生成器和版本，不手改；变更源文件后重新生成。
- CI 检查 schema 有效、生成结果无未提交 diff，并检查真实响应符合 schema。
- `operationId` 和 schema 名是生成代码的 API：稳定、唯一、表达业务，不用 `get1`。
- 生成器能力不同；先查项目锁定版本的官方文档，必要时用 Context7。不要为了“生成一切”把业务逻辑塞进模板。

OpenAPI 能表达接口形状，不会自动保证授权、事务或业务不变量；这些仍由实现和验证承担。

## 资源与命名

先找业务名词，再映射 HTTP：集合用复数名词，资源 ID 放 path，筛选/排序/分页放 query，复杂输入放
body；HTTP method 表达通用动作。

```text
好：GET /projects/{projectId}/tasks?state=open
差：POST /getOpenTasksForProject
```

Google AIP-122 要求资源名在 API 内唯一，集合段用复数，并建议 ID 用字符串。这里把它当一致性基线，
而不是强迫所有项目采用 Google 的完整资源名格式。字段 casing、时间、金额单位、null 与缺失的语义要在
schema 中统一声明。

非 CRUD 动作确实是领域概念时可建动作或子资源，例如 `POST /orders/{id}:cancel`；不要用动作逃避
资源建模。路径和字段一旦发布就是消费者依赖，重命名前先识别真实消费者。

## 分页与版本

所有可能增长的 collection 从第一版就分页。AIP-158 指出，后来把“返回全部”改为分页会让旧客户端
静默只拿到第一页，是行为不兼容。

游标模型适合持续变化或很大的集合：

```json
// GET /events?pageSize=50&pageToken=opaque-token
{"items": [], "nextPageToken": "opaque-token"}
```

- token 应不透明、URL-safe，只表示继续位置，不能充当授权；每页仍做对象级授权。
- 规定默认/最大 page size、稳定排序和 tie-breaker；除 page size 外，后续页筛选条件应保持一致。
- 不承诺精确总数时就不返回，或明确它是估算值。

版本解决**已发布且无法同步迁移**的消费者，不代替兼容演进。先选择并统一一种机制（路径、header 或
query）；Microsoft 指南展示的是 Azure 的 `api-version` query 方案，不是普适唯一答案。版本内优先
做兼容扩展；删字段、改变含义、optional 变 required、缩窄值域通常是不兼容变化。若生产者和所有
消费者同仓且可一起发布，按 `policy/working-contract.md` 直接迁移并收敛，不留下虚假版本层。

## 错误模型

HTTP API 可采用 RFC 9457 `application/problem+json`，不要再造形似但不兼容的 `error/message`
信封。核心成员是 `type`、`status`、`title`、`detail`、`instance`，并允许扩展字段。

```http
HTTP/1.1 409 Conflict
Content-Type: application/problem+json

{
  "type": "https://api.example.com/problems/out-of-stock",
  "status": 409,
  "title": "库存不足",
  "detail": "请求 3 件，当前可用 2 件",
  "instance": "/problems/01J...",
  "code": "OUT_OF_STOCK",
  "sku": "A-001"
}
```

- `type` 是 RFC 9457 规定的主要机器标识；项目另加 `code` 时也应稳定、唯一并写入 schema。
- 客户端按 `type`/`code` 分支，不解析可翻译、可改写的 `title` 或 `detail`。
- HTTP status 保留协议语义；同一种问题不要随 handler 改成不同状态。
- 校验错误可定义 `errors` 扩展，逐项给 JSON Pointer；RFC 9457 给出了这种模式。
- `instance` 可作为本次问题/支持定位标识，但不要泄露内部路径、SQL、stack、secret 或他人对象信息。
- 未预期异常记录内部 cause 与关联 ID，对外返回普通 5xx Problem Details。

### 非 HTTP 边界（Tauri 命令、IPC、Bot 消息）

RFC 9457 是 HTTP 规范，没有 status 和 URL 的边界不必硬套，但同一套思路仍然适用：
稳定的机器可读种类 + 给人看的说明 + 可选细节，客户端按种类分支。

- Tauri v2 命令返回 `Result<T, E>`，`Err` 会让前端 `invoke()` 的 promise reject；`E` 必须实现
  `serde::Serialize`。官方建议用 `thiserror` 定义自己的错误枚举，而不是到处 `map_err(to_string)`，
  这样可能出现的错误一目了然，并可序列化为带种类的结构映射到 TS 枚举：

  ```rust
  #[derive(Debug, thiserror::Error)]
  enum ExportError {
      #[error("聊天记录不存在")]
      NotFound,
      #[error(transparent)]
      Io(#[from] std::io::Error),
  }

  #[derive(serde::Serialize)]
  #[serde(tag = "kind", content = "message", rename_all = "camelCase")]
  enum ExportErrorKind { NotFound(String), Io(String) }
  ```

- 前端按 `kind` 分支，`message` 只用于展示；IO 等内部错误的原文先记日志，对用户只给可行动的说明
  （文案见 frontend-engineering 的 ux-writing）。

## 幂等

客户端看不到响应时不知道服务端是否已提交，因此“网络失败就重试”必须和服务端幂等一起设计。
GET/PUT/DELETE 的 HTTP 语义虽可幂等，实现仍要遵守；有副作用的 POST、webhook 与任务需显式策略：

1. 客户端为一次逻辑操作生成高熵 `Idempotency-Key`；重试沿用，新的逻辑操作换新键。
2. 服务端以调用者/租户 + operation + key 建唯一约束，保存请求摘要与最终 status/body。
3. 同一 key、同一载荷返回已保存结果；同一 key、不同载荷拒绝，防止误复用。
4. 明确并发占用、处理中、失败是否缓存，以及 key 的保留期；保留期应覆盖客户端最大重试窗口。
5. 不把 email、token 等敏感值放进 key。

Stripe API v1 是一个可验证实例：它保存首次开始执行后的 status/body（包括 500），比较参数，并允许
至少 24 小时后清理 key。不要照抄这些具体语义；要在自己的契约中明确选择。数据库唯一键和业务状态机
仍是最后防线，例如支付事件 ID 唯一、`paid` 不倒退为 `pending`。

## 短例子

TypeScript 客户端只消费生成类型：

```ts
import type { CreateOrderRequest, Order } from "./generated/api";
async function createOrder(input: CreateOrderRequest, key: string): Promise<Order> {
  return api.post("/orders", input, { headers: { "Idempotency-Key": key } });
}
```

Python/Rust 服务端的具体 schema validator、router 和生成器 API 随版本变化，应查官方文档；通用边界是：
HTTP adapter 把已验证 DTO 转成业务输入，再把业务结果映射回契约，不把 ORM row 直接序列化出去。

## 来源

- https://learn.openapis.org/introduction.html
- https://spec.openapis.org/oas/latest.html
- https://openapi-generator.tech/docs/usage/
- https://google.aip.dev/122
- https://google.aip.dev/158
- https://google.aip.dev/193
- https://github.com/microsoft/api-guidelines/blob/vNext/azure/Guidelines.md
- https://www.rfc-editor.org/rfc/rfc9457.html
- https://docs.stripe.com/api/idempotent_requests
- https://v2.tauri.app/develop/calling-rust/#error-handling
