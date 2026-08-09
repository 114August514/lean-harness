# Local Git capability 决定

> Issue: [#11](https://github.com/114August514/lean-harness/issues/11)
>
> 初始决定：2026-08-08
>
> Architecture reset：2026-08-09
> 状态：**原 Local Git MCP 决定已被取代**

## 当前决定

**不建设或保留 Local Git MCP。Skills 按 `git/contract.md` 通过 Bash 使用原生 Git。**

```text
git/contract.md / Skills
→ 选择明确 Git 命令

Bash / native Git
→ 执行并返回真实状态

GitHub MCP
→ 继续处理 Issue、PR、Checks 等 provider 能力
```

## 为什么取代原决定

原决定希望实现一个“窄范围 Local Git MCP”，用于 repository binding、结构化 facts 和
bounded mutations。实现和 review 过程中，acceptance boundary 逐渐扩展到：

- operation-specific timeout reconciliation；
- branch retention transaction；
- worktree loss-surface 与 cleanup policy；
- merge / rebase outcome classification；
- 统一 structured result 与大量 edge-case tests。

这说明 wrapper 正在重复拥有 Git 和 Skills 已经拥有的语义，而不是只补一个被真实流程
证明的缺口。

Architecture reset 时确认：

1. 全仓没有 Local Git MCP 的真实 consumer；tool 名称只存在于实现及其测试。
2. 已提炼到 `git/contract.md` 的日常 branch、status、diff、add、commit、merge、pull、
   push、worktree 和 cleanup 流程都可直接使用原生 Git。
3. Harness 已有 Bash 能力，可以为每次调用固定 `cwd`，并在不确定时执行只读观察。
4. Git 原生已经拥有 merge / rebase、worktree、refs、objects、conflict 和 command-specific
   safety/default semantics。
5. 保留 MCP 会额外维护 SDK、schema、parser、mutation layer、约三千行 Python
   代码和测试、lock file 与专属 CI，却没有实际使用证据。

继续瘦身未使用的 MCP 仍然受沉没成本影响。系统整体最简单的方案是删除实现，把必要
规则收敛到真实消费方读取的 `git/contract.md`。

## 保留的复用结论

原候选审计仍支持以下判断：

| 候选 | 审计 commit | 保留结论 |
| --- | --- | --- |
| `modelcontextprotocol/servers` git server | `76d64c822f5125032f89eb71dbdb94e42b434821` | 不作为依赖；当前 Runtime 直接使用 system Git 更短 |
| `blak0p/git-courer` | `80c84a4944503b302605f15932d6f858bf3dd573` | 不引入其 session、LLM、backup、release 等 monolithic workflow |
| `github/github-mcp-server` | `eb4c099e05ef622445e930b18682a0464f22418f` | provider capability 继续优先复用官方实现 |

这里的结论不是“永远不能有 Git adapter”，而是当前没有需求证明 Local Git MCP 是必要
组件。

## 当前实现边界

保留：

- system Git executable；
- Bash 工具；
- [`contract.md`](contract.md) 的标准流程、并行 worktree、事实保真和机械不变量；
- 官方 GitHub MCP 的 provider 能力。

删除：

- `git-mcp/` 实现和测试；
- Local Git MCP tool schema；
- `.github/workflows/git-mcp.yml`；
- 为该未使用 subsystem 建立的 timeout、cleanup 和 recovery semantics。

## 何时重新评估

只有出现真实证据时才新建 Issue：

```text
目标 Runtime 没有 Bash / native Git
或
多个真实 consumer 反复需要同一份稳定 Git machine schema
或
原生 Git 输出解析持续造成已发生的缺陷
或
必须建立独立权限、审计或 repository confinement 边界
```

重新评估时从实际调用记录和失败案例出发，不把 `git/contract.md` 当成需要逐条实现的
adapter backlog，也不恢复本次删除的兼容层。
