# Stage 5：Demo、发布与运行

本参考沿用 [`workflow/lifecycle.md`](../../../workflow/lifecycle.md) 的 Stage 5「种子装配、Demo 交付与差量审计」，
并补足发布后运行。验收编排使用 `skill://finish-work`，验证使用 `skill://verify-work`，审查使用
`skill://review-work`；本文只定义交付物应达到的质量。

## Demo 与交付不是同一件事

- **Demo** 回答“目标用户能否完成主旅程、结果是否有价值”；
- **交付** 回答“这个确切版本能否安全、重复地进入目标环境”；
- **运行准备** 回答“出问题时能否发现、定位、止损和恢复”。

面向用户的应用适合准备小而真实的种子场景和 30 秒入口。库、CLI、后台任务可能更适合用最小示例、
契约测试或产物安装验证，不必强造可视 Demo。

**产物**：可验收场景（Demo/示例/安装验证）、候选产物、验证与审查证据。README、CHANGELOG、
runbook 和发布说明的格式由 `skill://project-docs` 负责。

## 版本与可追溯产物

每个部署或分发产物至少能追溯到源码 revision、构建时间/流水线和配置版本。构建依赖应锁定，
同一输入应能重复生成等价产物；Google SRE 的 release engineering 也强调可重复、自动化、非
“雪花式”的构建与发布。

如果项目声明使用 SemVer，先明确 public API，再按其规则表达兼容性：

- 不兼容 public API 变化：major；
- 向后兼容的新功能：minor；
- 向后兼容的修复：patch；
- 已发布版本内容不原地替换，修改必须产生新版本。

内部应用、日期发布或平台商店版本可以采用别的方案，但需保持单调、唯一、可追溯；不要贴着 SemVer
标签却没有定义 public API。

**产物**：唯一版本号/构建 ID、不可变候选产物、从版本到源码与变更的映射。

## 发布设计

发布流程应是已定义、可重复的路径，而不是某台开发机上的命令历史：

1. 从已验证 revision 构建并保存不可变产物；
2. 对将实际发布的产物做必要系统/安装测试；
3. 分阶段或一次部署，方式与服务风险相称；
4. 做最小 smoke/health 验证并观察关键用户信号；
5. 记录版本、操作者/流水线、时间、配置和结果；
6. 失败时执行预先选定的 rollback 或 roll-forward。

小而频繁的变化更容易推理和恢复。DORA 建议以单个应用/服务为上下文观察交付表现，而非跨不同系统
排名；其当前五项指标是 change lead time、deployment frequency、failed deployment recovery time、
change fail rate、deployment rework rate。指标用于发现改进约束，不作为个人 KPI，也不值得为小项目
先建昂贵采集平台。

### Feature toggle 不是免费回滚

Feature toggle 可把部署与启用分开，适合渐进发布或实验；但 Fowler 的文章明确提醒 toggle 会增加
验证与配置复杂度。仅在需要独立控制启用时采用，测试重要的 on/off 路径，明确 owner 与清理条件；
短期 release toggle 完成后删除。数据库写入、迁移和外部副作用不能靠关开关自动撤销。

## 回滚、迁移与恢复

“可回退”先问状态是否已改变：

- **无持久状态变化**：重新部署上一份已知良好产物通常足够；
- **新旧版本需要并存**：schema/API 必须在共存窗口兼容；
- **已写入新格式或产生外部副作用**：可能只能 roll-forward、补偿或从备份恢复；
- **破坏性迁移**：先备份/验证恢复，分离 schema 变化与代码切换，逐步移除旧字段。

不要把每个 migration 都要求有 `down` 当作恢复保证：有损删除的 `down` 无法复原数据，伪造逆向脚本
反而制造信心。为每次变化选择并演练真实恢复路径，记录恢复点目标（RPO）和恢复时间目标（RTO）
仅当业务风险需要它们。

**产物**：runbook 中可执行的部署、验证、回退/前向恢复步骤；涉及持久数据时还有备份与恢复证据。
数据迁移细节转 `skill://backend-engineering`，文档结构转 `skill://project-docs`。

## 最小可观测性

Google SRE 建议面向用户服务优先关注四个黄金信号：latency、traffic、errors、saturation；
它们是起点，不是每个程序必须购买全套平台的清单。

按“出事时要回答什么”配置最小集合：

| 问题 | 最小信号 |
|---|---|
| 用户主旅程成功吗 | 黑盒检查或关键成功/失败计数 |
| 变慢了吗 | 成功与失败请求分开的尾延迟 |
| 负载如何 | 业务请求/任务吞吐，而非只有 CPU |
| 接近容量上限吗 | 最受限资源的饱和度与增长趋势 |
| 从哪个版本开始 | 部署事件、版本字段、结构化日志关联 ID |

告警只用于紧急、可操作、正在或即将影响用户且需要人介入的情况。仅供趋势分析或次日处理的信号进入
仪表盘/工单；告警噪声会掩盖真实事故。先监控症状，再用白盒指标和日志解释原因。

桌面应用或本地工具不一定有在线指标平台：崩溃报告（经同意）、明确错误、诊断导出和版本信息可能
更合适。不要以“可观测性”为名收集不必要的个人数据。

## Stage 5 出口

**足够好**意味着：

- 用户/操作者可按说明完成验收场景；
- 交付的是经过验证的同一份可识别产物；
- 部署、配置、迁移和恢复路径与风险相称并有最新证据；
- 关键失败能被发现，告警能导向明确动作；
- 运行知识已进入 runbook，而不是只留在本次 Agent 会话。

## 来源

- https://www.computer.org/education/bodies-of-knowledge/software-engineering/topics
- https://sre.google/sre-book/release-engineering/
- https://sre.google/sre-book/monitoring-distributed-systems/
- https://martinfowler.com/articles/feature-toggles.html
- https://semver.org/spec/v2.0.0.html
- https://dora.dev/guides/dora-metrics
