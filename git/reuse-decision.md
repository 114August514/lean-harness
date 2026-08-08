# Local Git MCP 复用决定

> Issue: [#11](https://github.com/114August514/lean-harness/issues/11)
> 日期: 2026-08-08
> 状态: Phase 1 完成（remediation 后）

## 决定

**实现一个窄范围的 Local Git MCP layer。**

## 理由

Whole-provider reuse is not suitable. Selective reuse beyond Git/MCP infrastructure provides little net value; implement the missing Git semantic boundary as a narrow Local Git MCP layer.

整体复用不适合。在 Git/MCP 基础设施之外的选择性复用净价值很小；
将缺失的 Git 语义边界实现为一个窄范围的 Local Git MCP layer。

详细论证见「方案比较」一节。

## 审计依据

为保证 Evidence 可复现，记录各候选审计时依据的 commit：

| 候选 | 仓库 | 审计 commit |
| --- | --- | --- |
| mcp-server-git | `modelcontextprotocol/servers` | `76d64c822f5125032f89eb71dbdb94e42b434821` |
| git-courer | `blak0p/git-courer` | `80c84a4944503b302605f15932d6f858bf3dd573` |
| github-mcp-server | `github/github-mcp-server` | `eb4c099e05ef622445e930b18682a0464f22418f` |

## 要求分层

Git Contract 对 Local Git capability 的要求分为三层，避免把「整个 provider
是否原生完整满足 Contract」作为淘汰标准：

### 1. Contract 硬性要求

任何最终实现都必须满足的语义保真要求：

```text
machine-stable / faithful Git facts
→ 使用 NUL 边界或等价无歧义结构；不解析面向人的装饰文本

unborn / absent / false / error 区分
→ 命令失败、权限不足、不存在是明确 error，不是空集合或 clean

authoritative after-observation
→ mutation 后重新读取真实状态，不把成功退出当作语义完整证明

no hidden workflow decisions
→ 不替调用方选择 branch/merge 策略、不自动 stash/abort/resolve
```

### 2. 操作特定安全

按操作分别评估，不要求所有 mutation 有统一的 expected-state / CAS API：

```text
branch deletion
→ expected ref identity、retained refs、reachability

worktree removal
→ 与操作匹配的实际 loss surface（tracked/untracked/ignored/submodule/nested）

merge / rebase
→ 相关前置条件 + conflict / in-progress 状态返回
```

### 3. 接口 / 工具表面改进

属于适配层可以解决的呈现问题，不构成 provider 淘汰理由：

```text
structured presentation
tool descriptions
filtering / read-only
pagination / truncation 标记
```

## 候选 capability 分解

不按 whole-provider PASS/FAIL，按能力级别分解每个候选。

### mcp-server-git（官方 MCP Git baseline）

来源：`modelcontextprotocol/servers` → `src/git`

| 能力 | 复用判断 | 证据 |
| --- | --- | --- |
| Git 机械操作（经 GitPython） | 可直接复用（但项目已直接复用 system Git executable，GitPython 是额外间接层） | 全部操作最终调用 system git |
| 仓库限制（`--repository`） | 可薄适配 | opt-in 本身不是问题——Runtime 启动实例时传入即可；但 subdirectory 检查允许越入 nested repo，linked worktree 在允许目录外时被误拒 |
| 读取事实 | 须替换 | 全部输出为人类可读文本（`TextContent`），不满足 Contract 硬性要求第 1、2 条 |
| 写入 mutation（add/commit/checkout/create_branch/reset） | 须替换 | 无 before/after 观察；不满足硬性要求第 3 条 |
| merge / rebase / conflict | 不存在 | 无对应工具 |
| worktree removal / branch deletion | 不存在 | 无对应工具 |
| 错误分类 | 须替换 | 未捕获分类，GitPython 异常直接传播 |
| 接口呈现（schema、描述） | 可薄适配 | 无 escape hatch；但输出非结构化 |

### git-courer

来源：`blak0p/git-courer`

| 能力 | 复用判断 | 证据 |
| --- | --- | --- |
| Git 机械操作（经 exec adapter） | 可直接复用（同上，system Git 已直接复用） | `exec.Command("git", args...)` argv 执行 |
| 仓库限制 | 可直接复用 | 固定单仓库 scope，无 per-call path 参数；有 GitCommonDir 感知 |
| 状态读取（status） | 可薄适配 | typed JSON 含 staged/untracked/conflict 计数；但无 detached/unborn 区分（detached 显示为空 branch）、无 ignored 枚举、无 in-progress 字段 |
| diff / history 读取 | 可薄适配 | JSON 包装但 diff 本体为文本；有分页和 truncated 标记 |
| 写入 mutation（stage/branch/integrate/rewrite） | 须替换 | 不满足硬性要求第 3、4 条：工具捆绑多个 mutation（branch CREATE+switch+stash+pop；integrate MERGE+delete source+push）；无 after-observation；隐藏 workflow 决策（auto-stash、auto-delete、auto-push） |
| merge / rebase conflict 返回 | 可薄适配 | 有结构化 ConflictResultJSON（conflicted_files 列表） |
| worktree removal | 须替换 | 使用 `--force`，无 loss-surface 枚举 |
| branch deletion | 须替换 | `git branch -d/-D`，无 expected tip / retained refs / reachability 验证 |
| 错误分类 | 部分可复用 | 少数特殊前缀（PUSH_REJECTED、MERGE_CONFLICT）；大多为 generic stderr 文本 |
| 接口呈现 | 可直接复用（作为设计参考） | 语义化工具、分页、truncation 标记、safety gate 模式 |
| 捆绑的 harness 语义 | 不引入 | LLM 生命周期、session 引擎、auto-backup、release wizard、TUI、MCP installer；且运行时无法以 Git-only 模式启动 |

### github-mcp-server（仅边界确认）

| 能力 | 确认 |
| --- | --- |
| Toolsets | ✅ `--toolsets` / `X-MCP-Toolsets` |
| 单工具过滤 | ✅ `--tools` / `--exclude-tools` |
| 只读模式 | ✅ `--read-only` / `X-MCP-Readonly` |
| 认证 | ✅ PAT / OAuth / GitHub App |
| 传输 | ✅ 远程托管 + 本地 stdio |

结论：GitHub capability 默认直接复用官方实现，不建设第二套。

## 方案比较

```text
方案 A：现有 provider + adapters / extensions / replacements

方案 B：窄范围 Harness-owned Local Git semantic layer
       + system Git executable
       + 官方 MCP SDK
```

### 以 mcp-server-git 为基底（方案 A1）

| 组成部分 | 性质 |
| --- | --- |
| 仓库限制修正（nested repo / worktree 判断） | 薄适配 |
| 结构化读取层（替代全部文本输出） | **替换核心读取路径** |
| mutation before/after 观察 | **替换核心 mutation 路径** |
| merge/rebase/conflict/in-progress | **新增全部** |
| worktree removal / branch deletion | **新增全部** |
| 错误分类层 | **替换错误处理路径** |

评估：mcp-server-git 是 GitPython 薄封装（约 600 行 server 代码）。
读取、mutation、错误处理三条核心路径都需要替换，还要引入 GitPython
作为额外依赖（而 system Git executable 已被直接复用）。适配后
基本不剩可复用的实质内容，还继承其 subprocess 间接层。

### 以 git-courer 为基底（方案 A2）

| 组成部分 | 性质 |
| --- | --- |
| 仓库限制 | 直接复用 |
| status / diff / history 读取 | 薄适配（补 detached/unborn、ignored、in-progress） |
| conflict 返回结构 | 薄适配 |
| mutation 解绑（拆分多-mutation 工具为单 mutation + 前置检查 + after 观察） | **替换核心 mutation 路径** |
| worktree removal 安全化（去 `--force`，加 loss surface） | **替换** |
| branch deletion 安全化（加 retained refs / reachability） | **替换** |
| 错误分类补全 | 薄适配 |
| 剥离 harness 语义（LLM 生命周期、session 引擎、backup、release、TUI、installer） | **长期维护负担**：monolithic 启动，须在上游每次更新时维护剥离 patch 或 fork |

评估：git-courer 的接口呈现设计（语义化工具、分页、truncation）可作为
设计参考直接复用。但其核心 mutation 路径与 Contract 硬性要求第 3、4 条
冲突（捆绑多 mutation、隐藏 workflow 决策），须替换；剥离捆绑的 harness
语义是长期的 fork/patch 负担。实际可复用的是「设计参考」而非「代码主体」。

### 方案 B

| 组成部分 | 性质 |
| --- | --- |
| Git 机械操作 | 直接复用 system Git executable |
| MCP 协议 / 传输 / schema | 直接复用官方 MCP SDK |
| Git 语义边界（结构化事实、before/after 观察、操作特定安全检查、错误分类） | 自实现——仅实现确认的语义缺口 |
| 接口呈现 | 参考 git-courer 的成熟设计（语义化工具、分页、truncation、safety gate 模式） |

### 结论

方案 A1 需要替换 mcp-server-git 的全部核心路径，剩余可复用内容趋近于零。
方案 A2 需要替换 git-courer 的核心 mutation 路径并长期维护 harness 剥离，
选择性复用的净价值很小。

两者都构成工作契约「复用优先」中允许重新实现的情形：

> 仅当复用会导致长期 wrapper、patch、fork 或更高整体复杂度，
> 或无法满足当前必要需求时，才重新实现。

因此确认决定：**实现一个窄范围的 Local Git MCP layer**。

## 复用内容（不变）

- **Git 机械操作** → 系统 Git executable
- **MCP 协议 / 传输 / schema 机制** → 官方 MCP SDK
- **MCP 互操作性验证** → MCP Inspector
- **GitHub 能力** → 官方 `github/github-mcp-server`（默认复用，不建设第二套实现）
- **接口呈现设计参考** → git-courer 的语义化工具、分页、truncation、safety gate 模式

## 实现范围

窄范围 Local Git MCP layer 只实现确认的语义缺口：

```text
结构化读取事实（Contract 硬性要求 1、2）
mutation before/after 观察（硬性要求 3）
操作特定安全检查（branch deletion / worktree removal / merge-rebase 前置与冲突状态）
错误分类
```

不实现：

```text
Git 机械操作（复用 system Git）
MCP 协议栈（复用官方 SDK）
workflow / checkpoint / DONE 判断（属于 Skills / Policy）
统一 expected-state / CAS API（按操作特定安全评估，不机械统一）
provider framework / comparison framework / registry
```
