# OMP 运行时接入

本目录只包含 OMP 原生项目配置和导航，不是新的 Harness 运行时子系统。

## 已验证版本

- 日期：2026-08-09
- 版本：`omp/17.2.11`
- Revision：该发行版的 `omp --version` 不提供源码 revision
- 入口：在仓库根目录运行 `omp`

## 适配调查

| 问题 | OMP 实际行为 | 当前决定 |
| --- | --- | --- |
| 项目配置 | 自动读取根目录 `.omp/config.yml`；项目配置覆盖全局配置，命令行参数可继续覆盖 | 只使用原生项目配置，不增加启动 wrapper |
| 项目上下文 | 会话启动时注入最近的 `.omp/AGENTS.md` | `AGENTS.md` 只做导航，权威内容保留在原文件 |
| Skills | `skills.customDirectories` 可直接扫描一层 `*/SKILL.md` | 直接加载仓库 `skills/`，不复制、不同步 |
| 审批 | OMP 提供 read / write / exec 审批和逐工具策略 | 不复制 Policy，也不增加 OMP 专用审批框架 |
| 上下文压缩 | 压缩 OMP 会话中的临时上下文 | 允许使用，但不能作为持久工作事实 |
| Memory | OMP Memory 会形成第二份项目级持久信息 | 显式关闭 Memory 和 autolearn，由 Continuity 统一持有持久工作状态 |
| 子任务 | OMP 隔离模式会隐式创建 workspace、branch、commit、stash、cherry-pick 或 patch | 关闭 task isolation；第一版只优先使用调查和评审类子任务 |
| Hook 与限制 | OMP 支持 Hook 和工具审批，但 Bash interception 不是完整安全边界 | 没有真实缺口前不增加拦截框架 |
| 原生 GitHub tool | 支持读取、搜索、PR create / checkout / push 和 Actions watch | 能力可用，但缺少完整的评论、Review 提交和托管合并操作 |
| MCP | 原生读取 `.omp/mcp.json`，支持 HTTP 和运行时解析凭据 | 使用官方托管 GitHub MCP 作为唯一 GitHub 操作面 |
| 交互入口 | `omp` 启动 TUI，`omp -p` 启动新的非交互会话 | 直接使用 OMP 原生入口 |

这些事实已经足够决定当前实现，因此没有继续比较第二个 Runtime，也没有设计通用 Runtime 或 Provider 抽象。

## GitHub Provider

`.omp/mcp.json` 接入官方托管的 [GitHub MCP Server](https://github.com/github/github-mcp-server)。

- Toolsets：`default,actions`，覆盖仓库、Issue、PR、Review、托管合并、Actions 和 Checks。
- 凭据：运行时通过 `gh auth token` 获取；仓库和 Continuity 中都不保存 token。
- 本地 Git：branch、index、worktree、commit、merge 和 push 仍遵守 [`substrates/git/contract.md`](../substrates/git/contract.md)，由原生 Git 执行。

`mcp.json` 放在 `.omp/`，因为它是 OMP 必须原生发现的运行时 binding。GitHub 能力本身由官方 MCP 持有，仓库没有自有的 GitHub contract，所以不建立 `substrates/github/`，也不维护配置副本。

首次使用前运行：

```bash
gh auth login
```

其他 OMP profile 可以在仓库外使用自己的凭据策略；提交到仓库的配置始终不含凭据。

## 状态边界

```text
OMP session / compaction
→ 运行时临时上下文

continuity/
→ Harness 持久工作状态
```

新的会话必须通过 Continuity、当前 Git 事实和当前 GitHub 事实恢复工作。恢复旧 OMP 会话只能作为便利，不能作为恢复证据。

## 验证

基础检查：

```bash
omp --version
omp -p --no-session "说明 Lean Harness 的架构入口，并列出发现的 Harness Skills。不要修改文件。"
uv run pytest -q
uv run ruff check .
uv run python -m compileall -q continuity
uv run python -m continuity --help
```

Dogfooding readiness 还要求两个场景：

1. 新 OMP 会话读取 Issue，按 Harness 权威完成实现、验证、评审、PR 和 Checks 观察，并得到真实的最终状态；
2. 丢弃旧对话后，新会话只依赖 Continuity、Git 和 GitHub 事实恢复当前工作，并给出下一项安全操作。
