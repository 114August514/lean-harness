# Git 使用索引

[`contract.md`](contract.md) 是本仓库使用 Git 的权威规范，包含普通 branch 流程、并行
worktree、提交、同步、冲突、清理、不确定结果和原生 Git 调用边界。

## Authority

| 问题 | 阅读位置 |
| --- | --- |
| 日常 branch、commit、merge、push、worktree 与 cleanup 怎么做 | [contract.md](contract.md) |
| Agent 调用 Git 时必须保持哪些事实和机械边界 | [contract.md](contract.md) |
| destructive operation 是否获得授权 | [`policy/decision-boundaries.md`](../policy/decision-boundaries.md) |
| checkpoint、Recovery、handoff 与 resume | [`continuity/contract.md`](../continuity/contract.md) |
| Git command-specific semantics | 原生 Git 文档与实际命令结果 |

## 常用入口

### 开始普通 Issue

阅读 `contract.md` 的“标准单 worktree 流程”：

- 开始前查看 status；
- 更新 `main`；
- 创建并切换到短期 branch；
- 只 stage 明确 path；
- 检查 staged diff 后 commit。

### 并行推进多个 Issue

阅读 `contract.md` 的“并行 worktree 流程”。每个 writer 使用独立 linked worktree 和
短期 branch，不共享 index，也不并发移动同一个 branch。

### 同步 main 或处理冲突

阅读 `contract.md` 的“同步主分支”和“Conflict 与中间状态”。当前标准路径使用显式
merge；Git 负责冲突 mechanics，Agent 负责理解和解决内容。

### PR 合并后清理

阅读 `contract.md` 的“PR 与合并后清理”和“清理 linked worktree”。worktree removal 前
显式查看 ignored，不使用 `--force`。

### 命令结果不确定

阅读 `contract.md` 的“不确定结果”：不盲目 retry，先用只读 Git 命令重读 HEAD、status、
refs 或 worktree registration。

## 当前技术决定

```text
Skills / git/contract.md
→ 决定 Git 意图和命令顺序

Bash / native Git
→ 执行真实命令

GitHub provider capability
→ 处理 Issue、PR、Review、Checks 和托管平台 merge
```

仓库当前不维护 Local Git MCP。没有真实 consumer 证明第二套 Git schema、parser、tests
和 CI 的维护成本合理。若未来出现 contract.md 列出的真实触发条件，再以新的 Issue
重新评估，而不是保留未使用的兼容层。
