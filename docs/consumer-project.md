# 在外部项目中使用 Lean Harness

本文定义第一个 dogfooding prerelease 的最薄消费方式。目标是让多个项目引用同一份、固定版本的 Harness，而不是复制 Policy、Skills、Continuity 和 Git contract。

## 版本与安装

当前 dogfooding 预发布版本使用：

```text
v0.1.0-dogfood
```

先从 [GitHub Release](https://github.com/114August514/lean-harness/releases/tag/v0.1.0-dogfood) notes 的 `Release commit` 复制完整 40 位 commit ID，并设置环境变量 `HARNESS_COMMIT`。每个版本安装到独立目录：

```bash
set -eu

: "${HARNESS_COMMIT:?set HARNESS_COMMIT from GitHub Release notes}"
HARNESS_VERSION=v0.1.0-dogfood
HARNESS_ROOT="$HOME/.local/share/lean-harness/$HARNESS_VERSION"

git clone --depth 1 \
  --branch "$HARNESS_VERSION" \
  https://github.com/114August514/lean-harness.git \
  "$HARNESS_ROOT"

test "$(git -C "$HARNESS_ROOT" rev-parse HEAD)" = "$HARNESS_COMMIT"
```

目录名和 tag 用于版本导航，GitHub Release notes 中记录的完整 commit ID 才是安装身份；校验失败时不得使用该目录。release 内的本文始终指向自身 tag，commit ID 在 tag 创建后记录到 Release notes，避免用后续 commit 修补当前 release。项目不引用 `main`，也不使用可变的 `current` 路径。

## Release 中的消费边界

Git tag 对应完整 repository snapshot，但外部项目只依赖以下长期 artifact：

| Artifact | 作用 |
| --- | --- |
| `policy/` | 权限、风险、破坏性边界和完成语义 |
| `skills/` | Agent 工作方法 |
| `continuity/` | 持久工作状态、恢复和共享事件实现 |
| `substrates/git/` | Harness 的 Git 使用契约 |
| `.omp/AGENTS.md` | OMP 导航入口 |
| `.omp/mcp.json` | 当前受限 GitHub Provider binding |
| `pyproject.toml`、`uv.lock` | 运行 Continuity 所需环境 |

`.github/`、tests 和 self-repository 的 `.omp/config.yml` 服务于 Lean Harness 自身开发，不是外部项目 authority。

## 项目 binding

目标项目只增加三个 OMP 文件，不复制 Harness authority：

```text
my-project/
└── .omp/
    ├── AGENTS.md
    ├── config.yml
    └── mcp.json
```

### `.omp/config.yml`

版本路径是项目 binding 的稳定引用：

```yaml
skills:
  customDirectories:
    - ~/.local/share/lean-harness/v0.1.0-dogfood/skills

workspace:
  additionalDirectories:
    - ~/.local/share/lean-harness/v0.1.0-dogfood

memory:
  backend: off

autolearn:
  enabled: false

task:
  isolation:
    mode: none

github:
  enabled: false
```

OMP 原生展开 `~`，直接加载 release 中的 Skills，并允许 Agent 读取 release authority。

### `.omp/AGENTS.md`

先声明固定 release root，再直接导入 release 的 OMP 导航：

```markdown
# 项目上下文

Lean Harness release root：`~/.local/share/lean-harness/v0.1.0-dogfood`。

@~/.local/share/lean-harness/v0.1.0-dogfood/.omp/AGENTS.md

## 本项目

在这里记录项目自身的架构、验证命令和约束。
```

`@` import 读取安装目录中的原文件，不产生第二份 Policy 或 Skills。

### `.omp/mcp.json`

当前 GitHub capability boundary 应随项目进入 review。第一版直接采用 release 中经过验证的 binding：

```bash
mkdir -p .omp
cp "$HARNESS_ROOT/.omp/mcp.json" .omp/mcp.json
```

这只是项目级 Runtime 配置，不是 Harness authority 副本。配置中不含 token；运行时使用当前 `gh` active account。修改 provider surface 时必须在项目中正常 review。

## 启动

准备 GitHub credential：

```bash
gh auth login
gh auth status
```

从目标项目根目录启动 OMP：

```bash
omp
```

Lean Harness 不绑定模型供应商。需要显式选择时使用 OMP 自己的 `--model` 参数，并选择当前 workstation 已配置的模型。

## 在目标项目中使用 Continuity

Continuity 从固定 release 运行，但 `--repo` 指向目标项目：

```bash
PROJECT_ROOT="$PWD"

uv --directory "$HARNESS_ROOT/continuity" run python -m continuity \
  --repo "$PROJECT_ROOT" recovery status

uv --directory "$HARNESS_ROOT/continuity" run python -m continuity \
  --repo "$PROJECT_ROOT" recovery bind \
  --work issue-1 --cycle cycle-1
```

共享事件仍发布到目标项目自己的 GitHub Issue；Recovery Log 写入目标项目的 Git common dir。Continuity 的固定 work-state port 只处理 canonical work-event 和最小恢复 facts；Agent 发起的普通 GitHub 操作仍统一使用项目 `.omp/mcp.json` 中的官方 GitHub MCP。

## 明确不做

第一版不提供 package registry、自动更新、安装器框架、Skill registry、版本解析器、项目生成器或兼容性承诺。真实外部项目的 dogfooding friction 决定下一次 bounded change。
