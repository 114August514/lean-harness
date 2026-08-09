# Git Contract

## 目的与 authority

本文件是 Lean Harness 使用 Git 的权威规范。它把日常开发、并行 worktree、清理和失败
恢复中真正需要长期保持的规则收敛在一处。

命令的具体行为和默认值以原生 Git 为准；本契约只规定 Harness 如何选择和组合这些
命令。它不是 Git 子系统规格，不要求建设 Local Git MCP、统一 result hierarchy、
recovery engine 或 workflow state machine。

涉及 Git 的其他判断按领域归属：

| 语义 | 权威来源 |
| --- | --- |
| branch、commit、merge、push、worktree 和 cleanup 流程 | 本文件 |
| command、ref、object、index、merge、rebase、worktree 的 mechanics | 原生 Git |
| destructive authorization、未知本地内容是否允许丢弃 | [`policy/decision-boundaries.md`](../policy/decision-boundaries.md) |
| checkpoint、Recovery、handoff 与 resume | [`continuity/contract.md`](../continuity/contract.md) |
| Issue、PR、Review、Checks 和 provider merge | GitHub provider capability |

## 执行边界

```text
Skills / Agent
→ 读取事实并决定要执行的 Git 操作

Bash / native Git
→ 在明确 repository 或 worktree 中执行该操作

Git
→ 决定 command-specific semantics、默认值、冲突和 ref / object mechanics
```

本仓库当前不维护 Local Git MCP。没有真实 consumer 证明第二套 tool schema、Git parser、
mutation layer 和专属 recovery semantics 比直接使用原生 Git 更简单。

Skills / Agent 负责：

- 该不该执行；
- branch、commit、merge / rebase、push 和 cleanup 策略；
- ownership、保留、checkpoint、handoff 与完成判断；
- conflict 如何解决；
- 不确定结果观察后采取什么下一步。

Git 和调用工具负责：

- 在指定 `cwd` 中执行明确命令；
- 保留 Git 的原生失败、冲突和中间状态；
- 不自动 stash、force、retry、abort、continue 或解决冲突；
- 不伪造成功，也不把失败静默压成空值。

## 最小事实模型

以下对象不能互相替代：

- **Repository**：共享 object database 和 refs 的仓库；
- **Worktree**：独立 working tree、index 和 `HEAD`；linked worktree 共享 repository；
- **Ref / branch**：可移动的名称，不是不可变 identity；
- **HEAD**：可以指向 branch、处于 detached state，或在首个 commit 前处于 unborn；
- **Index**：下一次 commit tree 的候选内容；
- **Working tree**：文件系统中的当前内容；
- **Commit**：由 tree、parents、author、committer、message 等决定的不可变 object；完整
  object ID 才是 identity；
- **Remote**：当前 repository 的命名配置，不等于远端 repository 或 GitHub provider
  state。

`staged`、`unstaged`、`untracked`、`ignored` 和 `conflict` 必须分开理解。普通
`git status` clean 不证明 ignored 内容不存在，也不自动证明 cleanup 安全。

## 原生 Git 调用规则

Agent 使用 Bash 调用 Git 时必须：

1. 每次明确设置目标 repository / worktree 的 `cwd`，或使用 `git -C <path>`；
2. mutation 前读取与决定相关的 status、branch / HEAD、refs 或 worktree facts；
3. 一次执行一个已经决定好的 Git 操作，不用 shell `eval`、隐藏脚本或复合 recovery；
4. 把 path、branch 和 revision 当作 operand；命令支持时用 `--` 结束 option；
5. 不输出带 credential 的 remote URL；
6. 不因命令失败自动重复可能已经生效的 mutation；
7. 不通过通用 `run_git` escape hatch 绕过本契约。

面向自动判断时优先使用 Git 的 machine-readable 能力，例如：

```text
git status --porcelain=v2 -z
git diff --raw -z / --name-status -z
git worktree list --porcelain -z
git for-each-ref
git rev-parse / symbolic-ref
git merge-base --is-ancestor
```

这是一组实现依据，不要求所有日常操作都解析成统一 JSON。人类可读的 `git status`、
`git diff` 和原生命令输出仍是标准工作方式。

## 标准单 worktree 流程

### 开始工作

先确认现场，再更新 `main` 并创建且切换到短期 branch：

```bash
git status
git checkout main
git pull --ff-only origin main
git checkout -b <type>/<issue>-<description>
```

禁止直接在 `main` 上开发。branch 必须对应一个明确 Issue / Work Unit；常用类型为
`feat/`、`fix/`、`docs/`、`refactor/`、`test/` 和 `chore/`。

若开始前 status 不是 clean，先识别现有 staged、unstaged、untracked、conflict 和
in-progress operation 的来源。不得用自动 stash、reset 或 clean 抹平未知现场。

### 开发与提交

开发期间反复读取：

```bash
git status
git diff
```

提交时只暂存明确准备提交的 path：

```bash
git add -- <明确文件或目录>
git diff --staged
git commit -m "<type>(<scope>): <description>"
```

不使用无边界的 `git add .` 吸收未知内容。一次 commit 表达一个完整、可验证的逻辑
变化；何时提交和 message 内容由 Skill / Agent 决定，不由底层工具生成。

首次推送先记录准备发布的完整 commit ID，再建立 upstream：

```bash
git rev-parse HEAD
git push -u origin <branch>
```

后续使用 `git push`，同样在调用前保留 intended commit ID。禁止 force push，除非
Policy 对明确目标给出单独授权。

### 同步主分支

开发 branch 需要吸收最新主分支时：

```bash
git checkout main
git pull --ff-only origin main
git checkout <branch>
git merge main
```

当前标准路径选择 merge，不默认 rebase。Git 负责 merge mechanics；若产生冲突，Agent
按本契约的 conflict 规则处理。

### PR 与合并后清理

Issue、PR、Review、Checks 和 squash merge 通过 GitHub provider capability 完成。本地
Git 不猜测 provider 状态。

PR 已确认合并后：

```bash
git checkout main
git pull --ff-only origin main
git branch -D <branch>
git fetch --prune
```

使用 `-D` 是因为 squash merge 后原 branch tip 通常不是 `main` 的 ancestor。它只允许
出现在“PR 已合并、主分支已更新、保留判断已完成”的清理路径中，不是通用删除策略。

## 并行 worktree 流程

普通单任务开发使用上一节。只有两个或更多独立 Work Unit 需要并行写入时，才创建
linked worktree。

### 创建

先更新主 worktree 的 `main`，再为每条并行写入路径选择明确 branch、path 和
start-point：

```bash
git checkout main
git pull --ff-only origin main
git worktree add -b feat/123-create-workspace ../lean-harness-123 main
git worktree add -b fix/207-run-status-sync ../lean-harness-207 main
```

`git worktree add -b <branch> <path> <start-point>` 使用 Git 原生创建 branch、registration
和 checkout。每个 worktree 有独立 working tree、index 和 `HEAD`，但共享 object
database 和 refs。

并行写入必须保持：

```text
一个 writer
→ 一个 worktree
→ 一个短期 branch

不同 writer
→ 不共享 worktree
→ 不并发移动同一个 branch
```

Git 原生会拒绝把同一个 branch 同时检出到两个 worktree；不得使用 `--force` 绕过。
普通只读检查直接使用现有 checkout，不为每个只读任务创建永久 worktree。

### 在目标 worktree 工作

```bash
git -C ../lean-harness-123 status
git -C ../lean-harness-123 diff
git -C ../lean-harness-123 add -- <明确文件>
git -C ../lean-harness-123 diff --staged
git -C ../lean-harness-123 commit -m "feat(workspace): 支持创建协作空间"
git -C ../lean-harness-123 push -u origin feat/123-create-workspace
```

需要同步最新 `main` 时，先在主 worktree 更新共享的 `main` ref，再在目标 worktree 显式
merge：

```bash
git checkout main
git pull --ff-only origin main
git -C ../lean-harness-123 merge main
```

### 清理 linked worktree

PR 合并后，先读取目标 worktree 的完整可见现场：

```bash
git -C ../lean-harness-123 status --short --branch --ignored
```

若存在 staged、unstaged、untracked、conflict 或来源不明的 ignored 内容，先保存、交接
或按 Policy 明确决定；不得直接删除。确认可清理后，从其他 worktree 执行：

```bash
git worktree remove ../lean-harness-123
git branch -D feat/123-create-workspace
git fetch --prune
```

不使用 `git worktree remove --force`。Git 允许 non-force removal 删除某些 ignored 内容，
因此 `status --ignored` 是清理前必要观察，不是 Git 自动替 Harness 完成的价值判断。
worktree 已意外消失、只剩失效 registration 时，确认目录确实不存在后才使用
`git worktree prune`。

worktree 不是 worker 的永久身份。任务完成、现场已处理且 PR 已收敛后，及时删除 linked
worktree 和本地短期 branch。

## Conflict 与中间状态

merge / rebase 算法、冲突产生方式和 abort / continue 语义由 Git 拥有。

Agent 遇到冲突时：

```bash
git status
# 理解并编辑每个冲突文件
git add -- <已解决文件>
git commit          # merge
git rebase --continue  # 仅当显式选择了 rebase
```

不希望继续时，明确使用相应的 `git merge --abort` 或 `git rebase --abort`。不得自动复制
一侧内容、自动 stash、自动 abort 或把 conflict 折叠成普通 command failure。

## 不确定结果

本地进程中断或调用方无法确认 mutation 结果时：

```text
不自动 retry
→ 重新读取 authoritative Git facts
→ Skill 根据真实状态决定下一步
```

按操作读取对应 facts，例如：

```bash
git status
git rev-parse HEAD
git branch --show-current
git show-ref --verify <ref>
git worktree list --porcelain
git ls-remote --exit-code origin refs/heads/<branch>
```

`push` 结果不确定时，将 `ls-remote` 返回的 remote object ID 与 push 前记录的 intended
commit ID 比较。相同表示目标 ref 已到达预期 commit；不同表示没有到达预期结果。若
remote observation 自身失败，结果仍为 uncertain，仍不得盲目重试 `push`。

这是 Harness 的调用方恢复步骤，不要求每个 mutation wrapper 内置 operation-specific
timeout state machine。调用方必须明确报告结果不确定和需要重新观察。

## Destructive operations

删除或覆盖本地状态前，调用方必须明确 target 和可见 loss surface，并按 Policy 判断
是否有权丢弃。底层调用不替代授权。

默认禁止：

```text
git reset --hard
git clean -fd
git worktree remove --force
git push --force
```

如果 mutation 的 target 在另一个 worktree 中处于 active checkout、Git 报告 dirty 或
conflict、ref 已移动，接受 Git 原生拒绝；不要通过 `--force` 绕过，也不要维护一套
预测 Git 行为的 preflight engine。

## Unsupported

Contract 不枚举纯 read-only observation command。只读取事实且不更新 refs、index、
working tree、worktree registration、remote 或 config 的 Git 原生能力可以按需使用，
例如 `git log`、`git show`、`git rev-list`、`git cat-file` 和 `git diff-tree`；调用仍须
遵守明确 `cwd`、credential 不外泄、option / operand 分隔和 no mutation 等通用边界。

当前 Contract 没有定义的 state-changing、destructive 或 workflow-significant Git
operation，应停止并明确报告 `unsupported` 及请求内容，先重新 align；不要临时发明
workflow，也不要为理论边缘情况建立 command allowlist 或永久抽象。

只有出现以下真实证据之一时，才重新评估专用 Git adapter：

- 目标 Runtime 没有 Bash / native Git；
- 多个真实 consumer 需要同一份稳定 machine schema；
- 原生 Git 输出解析已经持续造成缺陷；
- 必须建立独立进程权限、审计或 repository confinement 边界。

## 明确不包含

- Local Git MCP 或第二套 Git command API；
- workflow engine、ownership registry 或 distributed lock；
- generic Git result / error hierarchy；
- operation-specific timeout recovery engine；
- merge / rebase touch-set predictor；
- automatic stash、force、conflict resolution、checkpoint 或 DONE 判断；
- provider PR、release、deployment 或 remote authentication framework。
