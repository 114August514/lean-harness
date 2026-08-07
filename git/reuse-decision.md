# Local Git MCP 复用决定

> Issue: [#11](https://github.com/114August514/lean-harness/issues/11)
> 日期: 2026-08-08
> 状态: Phase 1 完成

## 决定

实现一个窄范围的 Local Git MCP layer。

## 理由

现有 provider 的 mutation 执行路径内部无法通过薄适配注入仓库限制、
compare-before-mutate 语义和结构化错误分类。差距在 mutation 执行路径本身，
不在接口层。

## 候选评估

### mcp-server-git（官方 MCP Git baseline）

来源：`modelcontextprotocol/servers` → `src/git`

| 维度 | 结论 | 关键证据 |
| -- | --- | --- |
| 仓库边界 | 部分满足 | `--repository` 为 opt-in；无 linked worktree 感知 |
| 结构化事实 | 不满足 | 全部输出为人类可读文本 |
| Mutation 边界 | 部分满足 | 单用途 tool，但无前置检查和操作后重读 |
| 过期状态保护 | 不满足 | 所有 mutation 均无 expected-state 参数 |
| 安全清理 | 不满足 | 无 worktree removal 和 branch deletion 工具 |
| 错误语义 | 不满足 | 无错误分类；原始 GitPython 异常直接传播 |
| 工具表面 | 部分满足 | 无 escape hatch，但输出非结构化 |
| 命令安全 | 部分满足 | argv 执行；部分路径缺 `--` 分隔符 |

### git-courer

来源：`blak0p/git-courer`

| 维度 | 结论 | 关键证据 |
| --- | --- | --- |
| 仓库边界 | 满足 | 固定单仓库 scope；无 per-call path 参数 |
| 结构化事实 | 部分满足 | status/history 为结构化 JSON；diff 为文本；无 detached/unborn 枚举；无 ignored 枚举；无 in-progress 字段 |
| Mutation 边界 | 不满足 | 工具捆绑多个 mutation（branch CREATE+switch+stash+pop；integrate MERGE+delete+push）；无 before→单 mutation→after 模式 |
| 过期状态保护 | 不满足 | 无 expected-state 参数；`confirmed=true` 是通用 consent gate，不是状态比较 |
| 安全清理 | 不满足 | worktree removal 使用 `--force`；branch deletion 缺少 tip/reachability/retained-refs 验证 |
| 错误语义 | 部分满足 | 少数特殊前缀（PUSH_REJECTED、MERGE_CONFLICT）；大多数错误为 generic stderr 文本 |
| 工具表面 | 部分满足 | 语义化工具，有分页和 truncation 标记；输出混合 typed JSON 和人类文本 |
| 命令安全 | 部分满足 | argv 执行；Add/Remove/Restore 缺 `--` 分隔符 |
| Harness 范围 | 部分满足 | 捆绑 LLM 生命周期、session 引擎、auto-backup、release wizard、TUI；无法以 Git-only 模式运行 |

### github-mcp-server（仅边界确认）

| 能力 | 确认 |
| --- | --- |
| Toolsets | ✅ `--toolsets` / `X-MCP-Toolsets` |
| 单工具过滤 | ✅ `--tools` / `--exclude-tools` |
| 只读模式 | ✅ `--read-only` / `X-MCP-Readonly` |
| 认证 | ✅ PAT / OAuth / GitHub App |
| 传输 | ✅ 远程托管 + 本地 stdio |

## 差距分析

以下 Git Contract 要求未被任何已评估 provider 满足，且无法通过薄适配补充，
因为它们需要对 mutation 执行路径的控制：

1. **结构化读取事实**：对 branch/detached/unborn HEAD、
   staged/unstaged/untracked/ignored/conflict、worktrees、refs、commit identity、
   ancestry、reachability、in-progress operation 的 typed 区分。

2. **Mutation 边界**：读取 before facts → 检查机械前置条件 →
   执行一个明确 mutation → 重新读取 after facts。两个 provider 均未执行
   此模式；git-courer 主动违反——每个 tool call 捆绑多个 mutation。

3. **过期状态保护**：调用方提供 expected HEAD / branch tip / index state；
   当 expected ≠ observed 时拒绝 mutation。两个 provider 均无
   expected-state 机制。

4. **安全清理**：worktree removal 需要 loss-surface 枚举（tracked changes、
   untracked、ignored、submodules、nested repos）。branch deletion 需要
   exact ref、expected tip、retained refs 和实际 reachability 验证。
   两个 provider 均未实现。

5. **错误分类**：调用方必须能区分 conflict、in-progress、stale precondition、
   missing object、wrong object type、dirty worktree、branch checked out
   elsewhere、unknown result。两个 provider 均折叠为 generic error text。

## 复用内容

根据 Git Contract 和工作契约的复用优先原则，以下成熟能力直接复用：

- **Git 机械操作** → 系统 Git executable
- **MCP 协议 / 传输 / schema 机制** → 官方 MCP SDK
- **MCP 互操作性验证** → MCP Inspector
- **GitHub 能力** → 官方 `github/github-mcp-server`（默认复用，不建设第二套实现）

## 实现内容

一个窄范围的 Local Git MCP layer，包装系统 Git executable，通过结构化
MCP 工具暴露 Git Contract 语义。该 layer 只实现上述已确认的语义差距——
不重新实现 Git 机械操作、MCP 协议或工作流编排。
