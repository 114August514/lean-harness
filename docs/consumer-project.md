# 在外部项目中使用 Lean Harness

目标是：下载一次、绑定项目一次，之后直接从项目根目录启动 `omp`。用户不需要手写 OMP 配置，也不需要日常手动调用 Continuity。

## 准备

- 已安装 OMP `17.2.11`；
- 已安装 `git` 和 `gh`；
- 首次使用 GitHub 时运行一次 `gh auth login`。

## 安装并启动

复制执行：

```bash
HARNESS_ROOT="$HOME/.local/share/lean-harness/v0.1.0-dogfood"

git clone --depth 1 \
  --branch v0.1.0-dogfood \
  https://github.com/114August514/lean-harness.git \
  "$HARNESS_ROOT"

cd /path/to/your-project
"$HARNESS_ROOT/bind-project.sh"
omp
```

完成。以后只需要在项目根目录运行：

```bash
omp
```

## Binding 做了什么

`bind-project.sh` 会：

1. 确认 Harness checkout 位于正式发布的 exact tag；
2. 自动读取 GitHub Release notes 中的完整 commit ID 并校验当前 checkout；
3. 在目标项目中原子创建三个薄 binding 文件：

```text
.omp/
├── AGENTS.md
├── config.yml
└── mcp.json
```

这些文件只引用已安装的 Harness release，不复制 Policy、Skills、Continuity 或 Git contract。启动后，Agent 会直接发现 Harness Skills，并按 release authority 使用官方 GitHub MCP、原生 Git 和 Continuity。

## 已有 `.omp/` 的项目

脚本不会覆盖现有 `.omp/`。如果项目已经有 OMP 配置，它会停止并保留原文件；应在正常 review 中合并现有配置与 Harness binding，而不是强制覆盖。

## 边界

这是一次性 project binding，不是 Runtime wrapper、安装器框架、自动更新器或 package manager。OMP 仍由用户直接启动，项目仍拥有自己的配置和 Git 状态。
