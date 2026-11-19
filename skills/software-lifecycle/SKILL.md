---
name: software-lifecycle
description: >-
  从软件想法到可交付版本的工程质量指南；用于新项目、需求塑形、架构与 ADR、walking skeleton、垂直切片、测试策略、发布运维、brownfield 接手，以及判断是否过度设计。触发词：软件生命周期、从零搭项目、工程基线、架构设计、交付上线、接手老项目、software lifecycle、walking skeleton、vertical slice、brownfield。
---

# 软件生命周期：每一阶段什么叫“好”

本 Skill 补充 [`workflow/lifecycle.md`](../../workflow/lifecycle.md)：后者定义五阶段流程与命令流，
这里说明每阶段应产出什么、什么质量才足够。具体执行仍交给
`skill://align-work`、`skill://implement-change`、`skill://verify-work`、
`skill://review-work`、`skill://finish-work`；不要在这里复制它们的流程。

## 何时使用

- 从一个想法开始，判断要不要做、先交付什么；
- 新建仓库、定模块边界、画 C4 图或决定是否写 ADR；
- 设计 walking skeleton、垂直切片与风险相称的测试；
- 准备版本、部署、回滚、监控或接手存量项目；
- Agent 给出“大而全”方案，需要按可逆性削减投入。

小型自用脚本不必走完整生命周期：保留能改变决定的步骤即可。已有项目通常跳过
Stage 3，先建立事实基线，再从下一条真实改动开始。

## 场景路由

| 场景 | 先读 | 产出 |
|---|---|---|
| 想法是否值得做；澄清用户、主旅程、非目标 | [需求塑形与契约](references/shaping-contracts.md) | 有证据的 go / no-go 判断；`spec` |
| 统一领域词汇、实体、不变量、模块责任 | [需求塑形与契约](references/shaping-contracts.md) | glossary / domain notes |
| 选架构、画图、判断 ADR 与公共契约 | [需求塑形与契约](references/shaping-contracts.md) | C4 Context/Container；必要的 ADR/contract |
| 新仓库工程基线与 walking skeleton | [骨架、切片与测试](references/skeleton-slices-testing.md) | 可运行最薄链路、标准动词、CI、配置契约 |
| 拆垂直切片、决定测试层次与重点 | [骨架、切片与测试](references/skeleton-slices-testing.md) | 可独立验收的切片；风险驱动测试组合 |
| 发版本、部署、回滚、监控、交接运维 | [交付与运行](references/delivery-operations.md) | 可追溯版本、发布记录、runbook、最小监控 |
| 接手老项目；控制工程投入与复用 | [存量接入与分寸](references/brownfield-proportion.md) | 事实地图、风险清单、下一条安全切片 |
| README、spec、ADR、glossary、runbook、CHANGELOG 模板 | `skill://project-docs` | 对应文档 |
| UI 结构、交互与文案 | `skill://frontend-engineering`；视觉审美用 `skill://frontend-design` | 前端行为 |
| API、错误、鉴权、幂等、迁移、日志 | `skill://backend-engineering` | 后端契约与运行行为 |

涉及具体框架或库 API 时，先用 Context7 MCP 的 `resolve-library-id`、`query-docs`
核对当前版本；临时 Python 工具优先 `uv run --with <包>`，不污染项目依赖。

## 五阶段的最小质量门槛

1. **Stage 1 需求塑形与定界**：能说清谁的什么现状要改变、主旅程、成功证据与非目标；
   产物是可验收意图，不是功能愿望清单。
2. **Stage 2 契约与不可逆决策**：只固定跨边界或高反悔成本的决定；契约、迁移、ADR
   都写明消费者、后果与回退/前向恢复方向。
3. **Stage 3 发射曳光弹骨架**：不是目录脚手架，而是一条穿过真实接缝、可构建、
   可测试、可部署的最薄链路；同时建立可复现工程入口。
4. **Stage 4 垂直切片与 TDD**：每片产生用户或操作者可观察结果，端到端闭合；
   测试保护业务风险和边界，不保护私有实现。
5. **Stage 5 Demo 与交付**：候选版本可识别、可重复部署、可回退、可观察；
   Demo 证明价值，运行证据证明它上线后仍可控。

## 贯穿规则

- **按反悔成本投入**：数据、公开契约、权限和生产变更先设计恢复路径；局部可逆代码用快速反馈。
- **逐步细化**：Context/Container 图先于类图；一条真实切片先于假想通用框架。
- **产物服务下一步决定**：没人会用的文档、指标、抽象或环境不创建。
- **复用优先但不盲从**：仓库既有能力 → 标准库 → 已有依赖 → 成熟生态；库的真实 API 用官方文档核对。
- **把发布能力前置**：构建、配置、CI、部署入口不是收尾工作，骨架阶段就跑通。
- **来源与事实分开**：外部规范支持通用规则；当前用户、流量、故障与约束必须来自本项目证据。

这些原则与 `policy/index.md`、`policy/always.md`、`policy/working-contract.md` 一致；
发生冲突时以 policy 和当前任务契约为准。

## 自检

- [ ] 当前阶段和 `workflow/lifecycle.md` 的五阶段命名、跳转一致
- [ ] 每个已执行阶段都有明确产物，以及“足够好”的可观察判据
- [ ] 非目标和投入强度与项目风险相称，没有把小工具做成平台
- [ ] 每个公共契约、持久状态和生产动作都有消费者与恢复方向
- [ ] 骨架/切片都穿过真实边界，不是横向堆文件
- [ ] 测试、发布和监控覆盖高后果风险，而非追求数量
- [ ] 文档模板交给 `project-docs`，前后端细节交给对应 Skill
