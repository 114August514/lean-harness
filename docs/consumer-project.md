# 在项目中使用 Lean Harness

## 前提

- Linux 与 GNU coreutils（`bind-project.sh` 使用 `mv -T -n`）；
- `git`；使用 OMP 时安装 OMP；release 模式需要已登录的 `gh`；
- 新项目所选技术栈的工具：`uv`、`bun`、`go` 或 `cargo`。

## 绑定已有项目

固定 release：

```bash
TAG=<release tag>
HARNESS_ROOT="$HOME/.local/share/lean-harness/$TAG"
git clone --depth 1 --branch "$TAG" https://github.com/114August514/lean-harness.git "$HARNESS_ROOT"
"$HARNESS_ROOT/bind-project.sh" /path/to/project --runtime omp
```

release 模式确认三件事：checkout 位于 exact tag；该 tag 的 GitHub Release 说明里有 `Release commit: <完整 sha>` 且与 checkout 一致；checkout 没有任何修改、未跟踪或被忽略的文件。任一条件不满足即退出，不写文件。

跟随开发中的 checkout：

```bash
/path/to/lean-harness/bind-project.sh /path/to/project --runtime all --dev
```

`--dev` 跳过上述校验，绑定记为 `dev-<commit>`；此后该 checkout 的任何变化都会直接影响这个项目。

绑定写入的内容：

| 运行时 | 文件 |
| --- | --- |
| OMP | `.omp/config.yml`：加载 Harness skills，关闭 memory、autolearn 和 task isolation；`.omp/AGENTS.md`：导入 Harness 的 `.omp/AGENTS.md`；`.omp/mcp.json`：GitHub MCP（OMP 只从项目 `.omp/` 读取 MCP 配置，所以这一份是复制） |
| Claude Code | `CLAUDE.md`：导入 Harness 的 `.omp/AGENTS.md`，首次启动时 Claude Code 会请求批准这个外部导入；`.claude/skills/<name>`：指向 Harness skills 的软链 |

项目里已有 `.omp/`、`CLAUDE.md` 或同名 skill 链接，或 `.claude` 不是目录时，脚本在写入任何文件前退出，不覆盖；把需要的几行手工合并进现有配置。中途失败或被中断时，脚本删除本次创建且之后未被改动的文件、链接和目录；期间被改动或加了内容的会保留，并在错误信息里列出。

## 新项目

```bash
/path/to/lean-harness/bin/new-project ~/Projects/my-app --stack ts-bun --runtime omp
cd ~/Projects/my-app
make setup && make check
```

目标目录必须为空（已有的 `.git` 可以保留）；已有项目用 `bind-project.sh`。`new-project` 依次复制 `templates/project-skeleton/`（Makefile、`docs/spec.md`、`docs/walkthrough.md`、`data/demo_seeds.json`、`.gitignore`）、`templates/adapters/<stack>.mk`（存为 `stack.mk`）和 `templates/stacks/<stack>/` 的可运行起点，再复制 `bin/doctor`、`bin/audit`，以 `--dev` 绑定，最后提交初始 commit。

| 技术栈 | `make check` 使用的工具 |
| --- | --- |
| `python-uv` | ruff、mypy、pytest（经 uv） |
| `ts-bun` | Biome、tsc、bun test |
| `go` | gofmt、go vet、go build、go test |
| `rust` | rustfmt、clippy、cargo check、cargo test |

| 命令 | 作用 |
| --- | --- |
| `make setup` | 安装依赖 |
| `make check` | 测试、lint、类型检查、格式检查；任一项失败即失败 |
| `make test` | 只跑测试 |
| `make dev` | 运行应用 |
| `make seed` | 通过应用加载 `data/demo_seeds.json` |
| `make demo` | `seed` 后运行应用 |
| `make doctor` | 检查 Git、`stack.mk` 用到的工具和绑定 |
| `make audit` | 扫描当前分支相对默认分支的改动（含未跟踪文件）：迁移、契约或密钥文件改动时退出码为 1；找不到默认分支或共同历史时退出码为 2，此时用 `make audit BASE=<ref>` 指定基准。检查范围写在 `bin/audit` 开头 |

## 日常工作

Agent 按 Harness 的流程 skill 推进：需要对齐时用 `align-work`，实现用 `implement-change`，诊断用 `debug-problem`，调查用 `investigate-question`，收尾由 `finish-work` 编排 `verify-work` 和 `review-work`。项目阶段划分与各阶段产物的质量标准见 `software-lifecycle`。

- `make check` 是代码变化收敛后默认的证据入口；
- `make audit` 报出的信号是审查线索，不替代审查；
- `docs/spec.md` 记录主旅程、非目标与切片进展，`docs/walkthrough.md` 记录阶段交付和待人工决定的事项。

## 边界

这是一次性 project binding，不是运行时包装、安装器或包管理器。项目仍由用户直接启动 `omp` 或 `claude`，并拥有自己的配置和 Git 状态。
