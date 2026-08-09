# Lean Harness

Lean Harness 为 Coding Agent 提供可审计的工作规则和工程方法，并直接复用成熟的运行时与外部工具。

## 架构

```text
Lean Harness
├── 核心能力
│   ├── Policy
│   ├── Skills
│   └── Continuity
├── 运行时接入
│   └── OMP
└── 外部能力契约
    ├── Git
    └── GitHub Provider
```

逻辑架构描述责任边界，目录只承载仓库实际拥有的长期文件：

| 责任 | 位置 | 作用 |
| --- | --- | --- |
| Policy | [`policy/`](policy/index.md) | 权限、风险、破坏性操作边界和完成语义 |
| Skills | [`skills/`](skills/) | 实现、调查、调试、验证、评审和收尾方法 |
| Continuity | [`continuity/`](continuity/index.md) | 持久事实、检查点、恢复、交接和继续工作 |
| OMP 接入 | [`.omp/`](.omp/README.md) | OMP 原生项目配置和入口导航 |
| Git 使用契约 | [`substrates/git/`](substrates/git/index.md) | 规定 Harness 如何使用 Git；命令由原生 Git 执行 |
| GitHub Provider | [`.omp/mcp.json`](.omp/mcp.json) | 通过官方 GitHub MCP 处理 Issue、PR、Review、Checks 和托管合并 |

GitHub Provider 在逻辑上属于外部能力，`mcp.json` 在物理上属于 OMP 运行时配置。仓库没有自有的 GitHub 规格，因此不建立 `substrates/github/`。

本仓库不提供通用 Runtime Adapter、Provider Registry、Git wrapper，也不复制 Policy、Skills 或 Continuity。OMP 会话和上下文压缩不能替代 Continuity。

## 使用 OMP

准备环境：

- OMP `17.2.11`，这是当前已验证版本；
- 安装 `gh`，并运行 `gh auth login`；
- GitHub token 具有目标仓库所需权限。

在仓库根目录运行：

```bash
omp
```

OMP 会读取 `.omp/config.yml` 和 `.omp/AGENTS.md`，直接加载现有 [`skills/`](skills/)，并连接官方 GitHub MCP。本地 branch、worktree、commit、merge 和 push 仍通过 Bash 调用原生 Git。

接入依据和验证方法见 [`.omp/README.md`](.omp/README.md)。
