---
name: project-docs
description: >-
  为软件项目设计、编写或评审项目文档：README、需求规格 spec、ADR、术语表、
  runbook、CHANGELOG、提交信息、代码注释与 AGENTS.md；适用于“该写什么文档”、
  “文档放哪里”、交接、发布说明、documentation、README、ADR、runbook、SemVer、
  Conventional Commits、docstring 等场景。
---

# 项目文档

让每份文档回答一个稳定的问题；按真实读者和风险增减，而不是给每个仓库铺满模板。
本 skill 只管“写什么、放哪里、怎样写清楚”。执行工作仍用 `implement-change`，
交付验证仍用 `finish-work`；仓库级协作规则以 `policy/` 为准，不在文档中复制一套。

## 何时使用

- 新项目需要最小文档集，或产品增长后需要补齐文档；
- 不清楚内容应放 README、spec、ADR、runbook 还是用户文档；
- 要建立发布记录、提交约定、注释或 agent 项目说明；
- 文档重复、过期、读者找不到答案，需要重构信息架构。

## 先按规模选择

| 场景 | 默认起点 | 出现什么再增加 |
|---|---|---|
| 一次性个人小工具 | README：用途、运行、输入输出、限制 | 被他人使用时补公共接口与 CHANGELOG |
| 可维护的库/CLI | README + public API reference + CHANGELOG | 有重要取舍时补 ADR；有领域歧义时补 glossary |
| 有用户的产品/服务 | README + spec + ADR 目录 + glossary + runbook + CHANGELOG | 用户任务增多时按 Diátaxis 拆用户文档 |
| 多包仓库/多团队系统 | 上述内容 + 分层 AGENTS.md + 各组件入口 | 只在局部事实确实不同处增加嵌套文件 |

不要创建空文档“占位”。有读者、有稳定问题、有维护者时再建；否则 README 中一个小节更容易保持真实。

## 哪个问题找哪份文档

| 读者的问题 | 放哪里 | 不放什么 |
|---|---|---|
| 这是什么，怎样首次跑起来？ | `README.md` | 设计争论、完整运维流程 |
| 要解决谁的什么问题，怎样算完成？ | `docs/spec.md` | 已选技术方案的辩护 |
| 当时为什么选这个结构/依赖/协议？ | `docs/decisions/NNNN-*.md`（ADR） | 操作步骤、当前需求清单 |
| 这个业务词准确指什么？ | `docs/glossary.md` | 实现细节和通用词典 |
| 怎样部署、回滚、恢复、排障？ | `docs/runbook.md` | 产品愿景、架构历史 |
| 某版本给使用者带来什么变化？ | `CHANGELOG.md` | 原样 Git 日志 |
| 怎样学习/完成任务/查参数/理解原理？ | 用户文档的 tutorial / how-to / reference / explanation | 项目内部决策流水账 |
| coding agent 在这个仓库必须知道什么？ | `AGENTS.md` | 通用编程常识、易过期的代码清单 |
| 这段非显然代码为什么这样写？ | 就近代码注释；公共 API 用该语言的 docstring/doc comment | 逐句翻译代码 |
| 本次无人值守工作做到哪、怎样验收？ | 本仓库既有 `docs/walkthrough.md` | 不另造永久项目文档 |

## 场景路由

| 要做的事 | 读取 |
|---|---|
| 选择文档集、划分用户文档、处理 README/spec/glossary/runbook | [references/document-map.md](references/document-map.md) |
| 写 ADR、CHANGELOG、SemVer、提交信息 | [references/decisions-and-releases.md](references/decisions-and-releases.md) |
| 写技术文字、代码注释、public API 文档、AGENTS.md | [references/writing-and-agents.md](references/writing-and-agents.md) |
| 需要短模板 | [templates/](templates/)；复制后删除不适用小节 |

## 最重要的规则

1. **先写读者和问题，再选文档名。** 同一事实只设一个权威位置，其他地方链接过去，减少漂移。
2. **README 是入口，不是仓库百科。** 让新读者能判断项目是否适用并完成第一次运行。
3. **spec 写目标与可观察验收，ADR 写一次重要决定及理由。** 两者混写会让需求变化和设计演化互相覆盖。
4. **runbook 的步骤要可执行。** 值班者需要命令、前置条件、成功信号和回退，而不是“按常规恢复”。
5. **面向使用者记录 notable changes。** CHANGELOG 与 commit history 的读者和粒度不同。
6. **注释解释契约、约束和反直觉原因。** 如果只是复述语句，优先改名或重构代码。
7. **AGENTS.md 只写项目事实。** 保留真实命令、局部约束和文档指针；通用流程链接 `policy/` 或相关 skill。
8. **库 API 与版本相关的写法先查真实文档。** 优先用 Context7 MCP 的 `resolve-library-id`、`query-docs`，不要凭记忆写参数或示例；临时 Python 文档工具用 `uv run --with`。

## 与本仓库骨架的关系

`templates/project-skeleton/docs/spec.md` 是 Lean Harness 的 shaping 与垂直切片契约，
`templates/project-skeleton/docs/walkthrough.md` 是阶段交付/无人值守验收记录；已有项目使用它们时继续沿用，
不要用本 skill 的通用 `templates/spec.md` 覆盖，也不要把 walkthrough 改造成 ADR 或 CHANGELOG。

## 自检

- [ ] 每份文档都有明确读者、问题和维护时机
- [ ] “哪个问题找哪份文档”只有一个权威答案，交叉处用链接
- [ ] tiny tool 没有被迫承担产品级文档仪式
- [ ] spec、ADR、README、runbook 的职责没有混淆
- [ ] 发布记录从用户视角编写，版本号基于声明过的 public API
- [ ] 代码注释与 AGENTS.md 没有复述显而易见或容易过期的信息
- [ ] 引用的命令、接口和链接已按当前项目事实核对
