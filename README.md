# Lean Harness

**Lean Harness** 是一个专为 Coding Agent（如 OMP、Claude Code 等）打造的轻量工程外骨格（Harness）。

它的设计原则是：**用静默的自动化护栏替代官僚式的过度审计，用客观的环境反馈（TDD/Linter/Diff）替代人肉盯梢，兼顾极速的开发流速与严谨的工程底线。**

---

## 架构

```text
Lean Harness
├── 核心工程准则 (Policy)
│   ├── always.md            # 三大横切底线：先搜再写 / 测试先行（先红后绿）/ 防手搓成熟基础设施
│   ├── triage.md            # 双轨分流：日常快轨 0 审批自愈环 vs 结构慢轨 1 页契约
│   ├── ai-failure-modes.md  # AI 高频失败模式排查手册（假测试、吞异常、删断言等）
│   └── evolution.md         # 防污染自进化与知识沉淀协议（三层进化模型、2-Strike 门槛）
├── 软件开发阶段规范 (Workflow)
│   └── workflow/lifecycle.md# 精益五阶段模型 (意图/契约/骨架/切片自愈/审计交付)
├── 自动化机械工具 (Tooling & Standard Verbs)
│   ├── make check           # 提交前一键门禁（fmt-check + lint + test）
│   ├── make doctor          # 仓库工程基线与健康度自检
│   ├── make audit           # Git Diff 高危信号与破坏性变更自动化扫描
│   ├── bin/new-project      # 一键脚手架：快速初始化具备 Lean Harness 规格的新项目
│   └── stack.mk             # 语言无关的标准动词适配器（Python/TS/Go/Rust）
├── 责任与能力闭环 (Skills)
│   └── skills/              # align / implement / verify / review / finish / debug
├── 事实连续性与可逆性 (Continuity & Substrates)
│   ├── continuity/          # Python 恢复引擎：per-worktree 恢复日志与状态重构
│   └── substrates/git/      # 原生 Git 契约：Linked Worktree 安全隔离与原子回退
└── 运行时接入与长程配方 (Runtime & Prompt Recipes)
    ├── docs/prompt-recipes.md  # 黄金驱动 Prompt 体系（塑形、先调研后干活、通宵挂机）
    ├── docs/runtime-recipes.md # Antigravity /goal 与 OMP 长程无监督协同配方
    ├── .omp/                # 原生接入 OMP (Oh My Pi) 运行时
    └── .claude/ & CLAUDE.md # 原生接入 Claude Code 运行时
```

---

## 标准动词接口 (Standard Verbs)

无论是人类还是 Agent，在任何项目中只需要记忆并遵循一套通用的动词：

| 动词命令 | 作用 | 推荐执行时机 |
| :--- | :--- | :--- |
| `make check` | **[最核心命令]** 完整门禁（测试 + Lint + 格式检查） | Agent 宣称完成任务前**必跑** |
| `make test` | 快速执行测试套件（含单元测试与工具链自检） | TDD 循环中频繁调用 |
| `make dev` | 启动本地开发或测试热重载模式（曳光弹运行） | 本地开发调试时 |
| `make seed` | 加载预置的具有真实业务语义的演示种子数据 | 演示或本地自测前 |
| `make demo` | 一键装配种子数据并拉起产品交互演示（带 30 秒玩转指南） | 交付或功能试玩验收 |
| `make doctor` | 检查仓库工程基线（Git、依赖、标准接口） | 接手新项目或环境排查时 |
| `make audit` | 自动扫描 Git Diff，检查 Schema 变更、新增依赖与假测试 | PR 提交前或人类合并代码前 |

> 详细实战流程指南请参阅 [使用 Lean Harness 进行全流程软件开发](docs/consumer-project.md)。

---

## 核心工程原则

1. **先搜再写**：写任何功能前，强制在代码库内搜索已有实现，严禁重复造轮子；加解密、时区计算、协议解析一律使用成熟库。
2. **测试先行且亲眼见证变红（Fail-to-Pass）**：严禁写出“未曾失败过”的伪测试；改完代码自动跑 `make check`，报错则在沙箱内自主修复。
3. **按可逆性决定投入（双轨制）**：
   - **快轨 (80%)**：日常 Bug 修复与小功能，0 人工卡点，完全依赖测试与编译机器门禁；
   - **慢轨 (20%)**：动数据库 Schema、破坏性 API 契约或权限模型时，前置编写 1 页以内的轻量 Spec 与回滚方案，确认一次即放行。

---

## 快速接入外部项目

你可以使用 `bind-project.sh` 将 Lean Harness 的工程能力一键挂载到任意目标仓库：

```bash
# 挂载到 OMP 运行时
./bind-project.sh /path/to/your-project --runtime omp --dev

# 挂载到 Claude Code 运行时（自动软链 Skills 并生成 CLAUDE.md）
./bind-project.sh /path/to/your-project --runtime claude --dev

# 同时支持双运行时
./bind-project.sh /path/to/your-project --runtime all --dev
```

---

## 快速从 0 创建新项目 (Scaffold)

使用 `bin/new-project` 可以在 5 秒内初始化一个具备标准动词、技术栈适配器与双运行时绑定的新项目：

```bash
# 初始化一个 TypeScript (Bun) 项目并挂载双运行时
./bin/new-project ~/Projects/my-app --stack ts-bun --runtime all

# 初始化一个 Go 项目并挂载 OMP 运行时
./bin/new-project ~/Projects/my-svc --stack go --runtime omp
```

---

## 模板与适配器 (Templates & Adapters)

在 `templates/` 目录下提供了语言无关的项目骨架与技术栈适配器：

- `templates/project-skeleton/`：包含标准 `Makefile` 与极简 `spec.md` 需求模板（带 Non-goals）；
- `templates/adapters/`：提供 `python-uv.mk`、`ts-bun.mk`、`go.mk`、`rust.mk`，填入 8 个变量即可让任何语言的项目接入统一的 `make check`。

