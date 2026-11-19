# 安全边界：身份、权限与输入

## Authentication 与 authorization 分开

- **认证（authentication）**回答“主体是谁”：验证 session、token 或服务身份。
- **授权（authorization）**回答“这个主体能否对这个对象做这个动作”。登录成功不代表可访问所有对象。

在入口把已验证的身份变成内部 principal；业务用例接收 principal 和目标对象，不在深层代码重新解析
header。权限默认拒绝，并在每次请求的服务端检查；前端隐藏按钮不是安全控制。安全需求可用带版本号的
OWASP ASVS 条目作为验收基线，例如写作 `v5.0.0-<requirement>`，避免标准升级后编号含糊。

## 对象级授权与 BOLA

OWASP API Security Top 10 2023 把 BOLA 列为 API1：攻击者修改 path、query、header 或 body 中的对象
ID，访问不属于自己的对象。随机 UUID 只能降低猜测概率，不能替代授权。

每个接收对象 ID 的操作都检查：

```text
principal × action × object (及 tenant / relationship / environment)
```

差与好：

```sql
-- 差：认证用户可按任意 ID 查询
SELECT * FROM projects WHERE id = $1;

-- 好：查询本身限定当前租户和成员关系
SELECT p.*
FROM projects p JOIN project_members m ON m.project_id = p.id
WHERE p.id = $1 AND p.tenant_id = $2 AND m.user_id = $3;
```

这不是要求授权只能放 repository；复杂策略可集中在 policy/service。关键是：调用路径无法绕过检查，
查询、修改、下载、批量操作、静态对象与后台任务都遵守同一策略。

覆盖以下反例：未认证、已认证但动作无权、同角色但访问别人的对象、跨 tenant、批量中混入无权对象。
403 或为避免泄露存在性而用 404 都可，但同类资源保持一致，并记录内部拒绝原因。

## 输入边界

OWASP 建议同时校验 syntax（类型/格式）和 semantics（值对该操作是否合理），使用 allowlist 描述接受
什么，而不是试图列尽恶意字符串。

边界顺序：

1. 在缓冲/解析前限制 body、文件、数组大小和解析深度，避免资源耗尽。
2. 用维护中的协议 parser 解码一次；解析失败立即停止。
3. 用 schema 校验 required、unknown field、类型、长度、范围、数组元素和嵌套对象。
4. 在业务层校验跨字段与状态规则，例如 `start < end`、订单仍可取消。
5. 在 sink 使用对应防护：SQL 参数化、HTML 输出编码等；“校验过”不等于对所有上下文安全。

不要把 transport DTO 自动绑定到 ORM/domain 对象，否则可能出现 mass assignment。显式挑选允许写入的字段：

```python
# 框架无关示意：validated 已由 schema validator 产生
command = UpdateProfile(display_name=validated.display_name)
# 不做：User(**request.json)，其中可能夹带 role="admin"
```

Rust/TypeScript 同理：serde/Zod 等具体 unknown-field、coercion 行为要查锁定版本文档。默认拒绝含糊的
自动转换；例如字符串 `"false"` 不应被意外当作布尔真。

## 错误与日志边界

授权失败和输入失败属于预期结果，返回契约定义的 Problem Details；意外异常对外不暴露 stack、SQL、
表名或 secret。日志记录主体的非敏感标识、动作、资源类型/标识、决策和关联 ID，但不要记录 token、
完整请求体或密码。具体见 [日志规范](logging.md)。

## 来源

- https://owasp.org/API-Security/editions/2023/en/0xa1-broken-object-level-authorization/
- https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html
- https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html
- https://asvs.owasp.org/
- https://www.rfc-editor.org/rfc/rfc9457.html
