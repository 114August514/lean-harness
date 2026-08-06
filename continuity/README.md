# continuity — 工作连续性

本目录是 Lean Harness 的工作连续性 module。

- `contract.md` — 权威契约（Runtime-neutral）。
- `continuity/` — 本地参考实现（stdlib-only Python 包）。
- `tests/` — 自动化场景测试，覆盖契约的恢复语义。

## 参考实现

`continuity/continuity/` 提供一条可运行入口，用于端到端验证：
绑定 worktree、记录 `intent` / `begin` / `end`、追加工作事件、
显式创建检查点、定位最近检查点、读取增量、发现 `begin` 无 `end`、
轮转恢复日志、加载恢复输入。

存储位置（可用 `CONTINUITY_ROOT` 覆盖）：

- 工作日志：`docs/journal/work-log/<work>/log.jsonl`（被 Git 跟踪）；
- 恢复日志：`docs/journal/recovery/<worktree>/log.jsonl`（被 `.gitignore` 排除）。

## 运行测试

```bash
cd tests
uv run --with pytest pytest -q
```

## 不属于本 module

Workflow Engine、Event Sourcing、Task Queue、跨机器同步、远程日志服务、
多存储后端、分布式一致性——见 `contract.md` 第十节。
