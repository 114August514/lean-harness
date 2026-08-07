# Git Contract Index

本文件是 Lean Harness Git 能力的常驻入口。

完整语义以 [contract.md](contract.md) 为准。本文件只保留核心模型、不变量和
按需阅读导航，不替代权威契约，也不定义具体命令、MCP API 或仓库工作流。

## 核心模型

```text
Work Unit
→ 目标、范围和验收，不等同于 branch、worktree 或 PR

worktree
→ 一位执行者修改 Git 工件的隔离现场

branch / detached HEAD
→ 当前 worktree 的提交起点和 ref 状态

commit
→ Git 工件快照与历史身份

Continuity checkpoint
→ 被显式发布为恢复边界的 coherent commit

PR
→ 一次交付与 Review 的 convergence sub-scope
```

因此允许：

```text
一个 Issue / Work Unit
→ 多个 branch
→ 多个 worktree
→ 多个 PR
```

这些对象没有固定的一一映射，也不共同组成持久工作流状态机。

## 核心不变量

- 稳定分支不作为普通开发现场；可变 active work 使用明确的 branch / worktree。
- 每个可变 worktree 同一时刻只有一个 owner；并行修改使用隔离的 worktree 和 ref ownership。
- checkout 或只读检查本身不建立 active work，也不隐式取得 ownership。
- Git facts 必须区分 repository、worktree、ref / detached state、HEAD、工作区状态和可达性。
- staged、unstaged、untracked、conflict、rename / copy 不得被折叠成一个 `dirty` 布尔值。
- ignored 不表示可丢弃；普通 status clean 与 safe cleanup 是两个不同判断。
- 任何覆盖或删除操作都先建立完整 loss surface，覆盖可能受影响的 paths、refs、commits、Recovery 和 remote state。
- commit 是 Git 历史；普通 commit 不自动成为 Continuity checkpoint。
- rebase、amend、cherry-pick 和 squash 可能重写或产生不同 commit identity；必须读取实际结果，只对实际受影响 checkpoint 追加 remap。
- PR 是 convergence sub-scope；merge 或 close 不自动表示 Issue / Work Unit `DONE`。
- 清理前必须证明本地修改、提交和 Recovery 已保留、可重建、明确交接，或已由有权 owner 授权丢弃；`force` 不得绕过该判断。
- Git 工具读取事实并执行明确操作；何时及为何执行、是否 coherent、是否完成由 Skills / Agent 判断。

## 按需阅读

### 创建或接管 active work

阅读 [contract.md](contract.md) 的：

- “Work Unit、branch、worktree 与 ownership”；
- “创建 branch / worktree”；
- “Artifact facts 与读取要求”。

### stage、commit 或形成 checkpoint

阅读 [contract.md](contract.md) 的：

- “stage 与 commit”；
- “Commit 与 Continuity checkpoint”；
- [`continuity/contract.md`](../continuity/contract.md) 的
  “Checkpoint、rotation 与历史改写”。

### merge、rebase、cherry-pick 或 squash

阅读 [contract.md](contract.md) 的：

- “History rewrite 与 identity”；
- “merge / rebase 与冲突”；
- “Commit 与 Continuity checkpoint”。

### handoff 或清理

阅读 [contract.md](contract.md) 的：

- “安全清理”；
- “Cleanliness、path inventory 与 loss surface”；
- “Destructive operations”；
- [`continuity/contract.md`](../continuity/contract.md) 的 release / handoff 不变量；
- [`policy/decision-boundaries.md`](../policy/decision-boundaries.md) 的禁止边界。

### 实现 Git MCP 或 Runtime Adapter

阅读 [contract.md](contract.md) 的：

- “Artifact facts 与读取要求”；
- “Mutation 的共同约束”；
- “Git MCP 最小能力边界”；
- “错误与操作后观察”。

## Authority

全局约束按以下顺序处理：

1. 当前 Issue / Spec 的明确目标和验收；
2. [`policy/decision-boundaries.md`](../policy/decision-boundaries.md) 的安全、权限、外部操作和 destructive boundary；
3. [`policy/working-contract.md`](../policy/working-contract.md) 的工程质量与完成语义。

其余语义不采用一条互相覆盖的全局顺序，而按领域定位权威来源：

| 语义域 | 权威来源 |
| --- | --- |
| Git object、ref、index、working tree、worktree、identity、ancestry、reachability 与机械安全 | [contract.md](contract.md) |
| Recovery、Shared Work Log、checkpoint 声明、remap、rotation 与 resume | [`continuity/contract.md`](../continuity/contract.md) |
| 操作时机、工程意义、验证、Review 与完成判断 | Skills |

交界事实由两层各自完成自己的判断，而不是互相覆盖。例如 Git Contract 判断 commit
是否存在和可达，Continuity Contract 判断它是否被显式声明为 checkpoint。本索引只
提供导航，不提升自身权威。
