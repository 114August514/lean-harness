# 技术专题：程序提示语与日志规范 (Logging, Exceptions & Prompts)

> 界面是对人的交谈，日志是对机器的审计。  
> **日志不是聊天窗口，严禁承载拟人助词与机器人设；动态变量进字段，静态短语做模板；内部排错只讲事实，外部交互恪守隔离。**

本文档汇总 CNCF OpenTelemetry Logs Data Model、IETF RFC 9457 (Problem Details)、Tokio `tracing` (Rust 官方诊断规范)、Go 官方错误规范以及 Google Style Guide 的核心约束，按**场景查阅式**组织。

---

## 查阅索引（按场景直达）

| 场景 / 痛点 | 查阅章节 | 核心规范与权威来源 |
|---|---|---|
| 服务/插件打印运行日志、排错信息 | [一、系统日志规范（Logging）](#一系统日志规范logging) | CNCF OpenTelemetry + Tokio Tracing + Pino |
| 函数内抛出异常、断言失败提示 | [二、代码异常与错误（Exceptions）](#二代码异常与错误exceptions) | Go 错误规范 + Clean Code 异常上下文 |
| 后端 API 接口返回的错误消息 | [三、API 接口错误规范（Problem Details）](#三api-接口错误规范problem-details) | IETF RFC 9457 + Google API Design |
| QQBot、终端命令行交互提示 | [四、Bot 与 CLI 交互提示（两界隔离）](#四bot-与-cli-交互提示两界隔离) | clig.dev + 机器日志与人际交互物理隔离 |
| 废弃旧函数、接口迁移提醒 | [五、废弃提示规范（Deprecation）](#五废弃提示规范deprecation) | SemVer 2.0.0 条款 8 + Javadoc 规范 |
| 代码内 TODO / FIXME 标记 | [六、代码注释与 TODO 规范](#六代码注释与-todo-规范) | Google Style Guide + Conventional Comments |
| 提交前自查代码与日志合规 | [七、日志合规自查清单（Checklist）](#七日志合规自查清单checklist) | 杜绝卖萌、无标点、敏感信息脱敏 |
| 查阅官方原著完整条目 | [八、权威来源](#八权威来源) | OpenTelemetry / RFC 9457 / Tokio / Go 官方真迹 |

---

## 一、系统日志规范（Logging）

权威来源：*CNCF OpenTelemetry Logs Spec* & *Tokio tracing Documentation*

### 1. 核心铁律
1. **严禁拟人化与口语助词**：严禁出现“啦、呀、哦、哈、糟糕、哎呀、Oops、！”等情绪化用语，日志系统不是聊天室。
2. **正文（Message）是静态事件索引**：日志正文必须是固定、简明的小写英文短语或中立动宾短语，**末尾严禁加句号**。
3. **动态变量必须提取为字段（Key-Value Attributes）**：严禁将 ID、数值直接用字符串拼接进正文，否则 Loki/ELK 无法通过模板聚合。
4. **日志级别严格判定**：
   * `DEBUG` / `TRACE`：仅用于线下排障的原始报文（Raw JSON、Socket 帧、函数出入参）。
   * `INFO`：系统生命周期关键事件（服务启动、连接就绪、单次有效业务完成）。
   * `WARN`：非预期但不影响当前事务的异常（触发限流、重试成功、配置缺失回退默认）。
   * `ERROR`：**当前单次操作已彻底失败**，流程中断，需要报警或人工介入。

### 2. 标准代码示范

#### Rust（标准方案：`tracing` crate）
```rust
// ❌ AI 典型“聊骚式”写法（严禁）：
info!("收到来自群 {} 用户 {} 的消息啦！内容是: {}", group_id, user_id, msg);
error!("糟糕！连接 Redis 失败了，错误是: {:?}", err);

// ✅ 工业级结构化写法（字段提取 + 静态动宾）：
info!(
    group_id = %group_id,
    user_id = %user_id,
    msg_id = %msg_id,
    "group message received"
);

warn!(
    attempt = 3,
    max_attempts = 5,
    "gateway timeout, retrying"
);

error!(
    error = ?err,
    target_db = "redis",
    "failed to connect database"
);
```

#### TypeScript（标准方案：`pino` 或类似结构化 Logger）
```typescript
// ❌ AI 随性写法（严禁）：
console.log(`[Bot] 用户 ${userId} 正在签到，处理中...`);
console.error("网络请求挂了，准备重试！");

// ✅ 工业级结构化写法（对象元数据前置 + 静态事件名）：
logger.info({ userId, command: "sign_in" }, "command execution started");

logger.warn({ attempt: 3, maxAttempts: 5, latencyMs: 1200 }, "upstream request slow, retrying");

logger.error({ err, userId }, "failed to execute sign_in");
```

---

## 二、代码异常与错误（Exceptions）

权威来源：*Go Code Review Comments (Error Strings)* & *Clean Code Chapter 7*

### 1. 异常提示三要素公式
```text
异常提示 = [操作/函数名] + [哪个参数不合法] + [期望值 vs 实际传入值]
```

### 2. 编写准则
* **全小写开头、末尾无标点**（方便多层调用链级联包装 `fmt.Errorf("reading config: %w", err)`）。
* **精准包含实际入参值**，绝不让调用者猜谜。

```rust
// Rust (anyhow / thiserror):
anyhow::bail!("invalid port number '{}', expected range 1024-65535", port);

// TypeScript:
throw new IllegalArgumentException(
  `invalid 'startDate' (${startDate}), must be earlier than 'endDate' (${endDate})`
);
```

---

## 三、API 接口错误规范（Problem Details）

权威来源：*IETF RFC 9457* & *Google Cloud API Design Guide*

微服务间或后端对前端返回错误载荷时，必须遵守项目的错误码 / 错误信封契约定义处：

```json
{
  "code": "INSUFFICIENT_FUNDS",
  "message": "Account balance (15.00 CNY) is lower than order amount (50.00 CNY).",
  "details": [
    { "field": "account_balance", "issue": "balance_too_low" }
  ]
}
```

* **`code`**：机器识别的常量，供调用端走 `switch-case`（如 `USER_NOT_FOUND`）。
* **`message`**：面向开发者的客观排障说明，说明原因与数值。
* **安全红线**：**严禁将底层 SQL 语法报错、数据库表名或未捕获的 Panic 堆栈暴露在 message 中**。

---

## 四、Bot 与 CLI 交互提示（两界隔离）

权威来源：*Command Line Interface Guidelines (clig.dev)*

开发 QQ 机器人、微信机器人或命令行工具时，最忌讳“内外不分”。

| 维度 | **程序内部日志（System Log）** | **外部交互消息（Bot/Chat Message）** |
| :--- | :--- | :--- |
| **流向** | 终端 `stdout/stderr`、日志收集系统 | 发送给 QQ 客户端/群聊窗口 |
| **受众** | 开发者、SRE、系统维护者 | 普通群友、终端操作者 |
| **风格** | 极度冷静、小写结构化、无情绪 | 可带有业务人设、Emoji、排版换行 |
| **红线** | **严禁带人设（禁止“主人我收到消息啦”）** | **严禁把内部异常堆栈甩在群里** |

### 交互报错的标准结构：
在群里回复用户指令错误时，必须给出**“一条可运行的正例”**：
```text
❌ 差：参数错啦！
✅ 优：缺少目标用户。正确格式：/ban @用户 [理由]（例：/ban @张三 广告刷屏）
```

---

## 五、废弃提示规范（Deprecation）

权威来源：*Semantic Versioning 2.0.0 (SemVer Rule 8)*

重构代码标记废弃方法时，必须满足四要素：
$$\text{被废弃项} + \text{从何版本废弃} + \text{替代方案} + \text{计划删除版本}$$

```typescript
/**
 * @deprecated Since v1.4.0, will be removed in v2.0.0. Use `fetchUserProfile(id)` instead.
 */
export function getUser(id: string) { ... }
```

---

## 六、代码注释与 TODO 规范

权威来源：*Google Style Guide (TODO Comments)* & *Conventional Comments*

* **严禁无名氏 TODO**：必须标注责任人与关联需求/Issue ID。
* **标准语法**：
  ```rust
  // TODO(august, #102): 重构为批量拉取以降低 API 调用频次
  // FIXME(august): 网络重连后状态机可能偶发处于悬挂态
  // NOTE: 此处故意不加锁，因为外部调用者已持有写屏障锁
  ```

---

## 七、日志合规自查清单（Checklist）

在提交代码前自查：

- [ ] **无聊骚口语**：全局代码中是否去掉了“啦/呀/哦/哈/糟糕/哎呀/Oops/！”等口语助词？
- [ ] **无裸插值日志**：Rust 是否全部使用 `tracing::info!(k = v, "msg")`，TS 是否全用对象前置？
- [ ] **正文无末尾标点**：所有 `logger.*` 与 `anyhow::bail!` 结尾**均无句号**？
- [ ] **两界彻底隔离**：终端系统日志与 QQ 发送消息是否严格隔离，无身份错乱？
- [ ] **敏感数据脱敏**：日志与报错中是否绝对屏蔽了 `token`、`password`、`secret`、`session_key`？

---

## 八、权威来源

如需深入求证协议细节或官方完整实现，可查阅官方原文：

* **CNCF OpenTelemetry Logs Data Model**：[查看官方原文](https://opentelemetry.io/docs/specs/otel/logs/data-model/)
* **IETF RFC 9457 (Problem Details for HTTP APIs)**：[查看官方原文](https://www.rfc-editor.org/rfc/rfc9457.html)
* **Tokio tracing (Rust 官方诊断规范)**：[查看官方原文](https://docs.rs/tracing/latest/tracing/)
* **Go Code Review Comments (Error Strings)**：[查看官方原文](https://go.dev/wiki/CodeReviewComments#error-strings)
