# 数据演进、配置与密钥

## 先写不变量，再画表

数据模型应表达业务事实和归属，而不是照搬页面表单。对每个实体明确：

- 身份与 tenant/owner；生命周期和允许的状态迁移；
- 唯一性、必填、范围、引用完整性；
- 时间、金额和删除语义；谁是事实来源。

能由数据库可靠表达的不变量，用 `NOT NULL`、`UNIQUE`、`CHECK`、foreign key 等约束兜底；应用层仍
提供友好错误。金额用明确币种和最小单位整数或合适的 decimal，不用二进制浮点。时间保存明确时区/
UTC instant；面向用户的时区转换留在边界。

DTO、domain model 与 persistence model 的变化方向不同，不要让 ORM row 自动成为 API 响应：

```rust
// 示意：公开 DTO 不会因为表新增 password_hash 而泄露字段
struct UserRow { id: String, email: String, password_hash: String }
struct UserResponse { id: String, email: String }
```

索引来自真实查询和约束；不是“每列都加”。检查列表查询的稳定排序、分页、N+1 和执行计划。

## Migration 是生产代码

Fowler 与 Sadalage 的 evolutionary database design 要点包括：所有数据库变化都用 migration、和应用
代码一起版本控制、自动执行，并让 schema 与数据共同演进。每个变化小而单一，migration 一旦在共享/
生产环境执行就视为不可改历史；修正用新的 migration。

“可回滚”不是机械要求每个文件都有 `down`。删列或丢数据无法靠 `down` 无损恢复。每次变更应明确真正
可行的恢复策略：安全 down、向前修复、备份恢复，或流量回切。迁移前确认备份和恢复路径适配风险。

## Expand → migrate → contract

当旧、新应用版本会同时运行，或有独立消费者时，用 parallel change：

1. **Expand**：先增加兼容结构，例如 nullable 新列/新表；旧代码仍可运行。
2. **Migrate**：部署兼容代码，双写或由单一写路径同步；分批回填；观测一致性；切读。
3. **Contract**：确认旧版本和消费者已退出，再停止旧写入、移除旧列/约束/兼容代码。

```text
禁止一步完成：rename email -> primary_email
安全演进：add primary_email → dual-write/backfill → read new → stop old writes → drop email
```

双写不是永久架构；必须有收缩条件。若生产者、消费者和数据库都未形成真实外部依赖且可一次更新，
直接改完并收敛，不制造无意义的过渡期。

大表 migration 注意锁时间和事务体积：避免一次回填全部行；分批、可续跑，并观察复制延迟和错误。
具体 DDL 锁行为与 migration API 强依赖数据库/框架版本，查官方文档或 Context7，不凭通用经验猜。

## 配置与 secrets

配置是部署间会变化的值；代码内固定的路由和业务规则不是“为了可配置而可配置”。Twelve-Factor 建议
配置与代码分离，并以环境变量作为语言无关载体。实际平台也可用挂载文件或配置服务；关键是不把环境值
编译进代码，并保持每个配置项独立、可审计。

启动时一次性解析并校验配置，失败要说明配置键和约束，但不回显 secret：

```ts
const cfg = ConfigSchema.parse(process.env); // 入口一次完成，内部拿 typed config
```

```python
config = AppConfig.from_env()  # 启动即失败；业务代码不反复 os.getenv
```

- 提供只含键名/非敏感示例的样例配置；不要提交真实值。
- secret 使用平台 secret manager，按最小权限授予应用身份；不要放源码、镜像层、普通日志或错误响应。
- 设计创建、轮换、撤销、过期和审计；OWASP 特别建议集中/标准化管理并尽量自动轮换。
- secret 泄露按事故处理：先撤销/轮换，再清理历史；仅从 Git 最新版本删除不等于失效。
- 开发、测试、生产使用不同凭据；测试不能碰生产数据或公网服务。

## 变更检查问题

- 新约束在现有数据上成立吗？回填如何处理异常行？
- 滚动部署期间，旧代码看见新 schema、新代码看见旧数据都安全吗？
- migration 中断后能否识别进度并安全重跑？
- 删除前是否证实所有读写方已切走？恢复方案能恢复数据而不只是 schema 吗？
- 配置缺失/非法是否在启动时失败？secret 是否有 owner、用途、轮换和撤销路径？

## 来源

- https://martinfowler.com/articles/evodb.html
- https://martinfowler.com/bliki/ParallelChange.html
- https://12factor.net/config
- https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html
