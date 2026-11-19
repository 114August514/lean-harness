# Lean Harness

Lean Harness 是给 Coding Agent（OMP、Claude Code 等）使用的轻量工程规范：一组按风险触发的规则、按需加载的 Skill、一个工作连续性实现，以及让项目检查真正生效的脚本与模板。

原则：按风险和可逆性决定投入，不给每次改动加仪式；能由测试、lint 和类型检查拦住的问题，不写成要模型记住的规则。

## 目录

```text
policy/                     规则
├── index.md                入口：核心原则、按需阅读、优先级
├── working-contract.md     工程质量、复用、测试与验证、完成语义
├── decision-boundaries.md  Agent 自主决定与必须请人决定的边界
├── ai-failure-modes.md     审查用的 AI 常见失败模式
└── evolution.md            如何把经验沉淀进 Harness
skills/                     按需加载的 Skill
├── _shared/                工作单元契约、委派格式、责任顺序
├── 流程                    align-work、implement-change、debug-problem、
│                           investigate-question、verify-work、review-work、finish-work
└── 工程知识                software-lifecycle、project-docs、frontend-engineering、
                            backend-engineering、llm-prompts-in-code
continuity/                 工作连续性：本地恢复日志与共享工作日志（Python，uv）
substrates/git/             原生 Git 使用契约
.omp/                       本仓库的 OMP 配置；绑定的项目导入其中的 AGENTS.md
bind-project.sh             把项目绑定到本 checkout（OMP、Claude Code 或两者）
bin/                        new-project、doctor、audit、test
templates/                  new-project 用的项目骨架、技术栈适配器与可运行起点
tests/test_tooling.sh       脚本、绑定与模板的行为测试
docs/consumer-project.md    在项目中使用 Lean Harness
```

## 在项目中使用

绑定已有项目：

```bash
/path/to/lean-harness/bind-project.sh /path/to/project --runtime omp   # 或 claude、all
```

绑定只写引用，不复制规则。默认要求 Harness checkout 处于正式 release tag；用开发中的 checkout 绑定时加 `--dev`。

从模板生成新项目：

```bash
/path/to/lean-harness/bin/new-project ~/Projects/my-app --stack python-uv   # 或 ts-bun、go、rust
cd ~/Projects/my-app && make setup && make check
```

生成的项目提供 `make setup / check / test / dev / seed / demo / doctor / audit`。安装方式、绑定内容和各命令的含义见 [docs/consumer-project.md](docs/consumer-project.md)。

## 开发本仓库

```bash
make setup   # uv sync
make check   # ruff、continuity 测试、tests/test_tooling.sh
```

`tests/test_tooling.sh` 会为四个技术栈各生成一个项目并跑它们的 `make check`，需要 `uv`、`bun`、`go`、`cargo` 和网络；本地缺少某个工具链时该项记为 SKIP，CI 中记为失败。

若有工具把本仓库的 skill 软链到主检出（例如 agent-config 的 `external-skills`），主检出应保持在 `main`，改动放在 linked worktree 中进行（见 `substrates/git/contract.md` 的“并行 worktree 流程”），合并后在主检出执行 `git pull --ff-only`。
