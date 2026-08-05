---
name: implement-change
description: 实现有边界的持久变化：feature、refactor、migration、配置或 Schema 变化、正式工具、文档交付。按 C0/C1/C2 启发式选择工作强度，形成可验证候选结果后交给 finish-work。
---

# Purpose

实现有边界的持久变化，并在收敛后形成可验证的候选结果。

`implement-change` 负责执行阶段：理解目标、选择匹配的工作强度、
完成实现、识别并更新受影响方。它不输出最终状态——执行完成只表示
"候选结果可验证"，完成判断属于 `finish-work`。

# Use when

- 新增 feature；
- 重构或迁移；
- 配置、Schema 或数据格式变化；
- 建设需要长期保留的正式工具；
- 文档交付；
- 需要长期保留的 prototype。

# Do not use when

- 目标是解释并修复异常行为——用 `debug-problem`；
- 目标是减少不确定性、获得答案或比较方案——用 `investigate-question`；
- 变化是临时验证手段且不打算保留——那是施工工具，不是本 Skill 的交付物
  （见 `policy/working-contract.md` 的"临时工具"）。

# Inputs

- Work Unit Contract（含 Implementation extension）；
- 相关代码、文档和既定事实；
- `align-work` 的对齐结论（如发生过）。

# Process

1. **判断初始 Development level。** 等级是启发式判断工具，不是流程状态：

   #### C0 — Local

   ```text
   单一责任内的局部变化
   消费者明确
   无状态迁移
   无公共或外部契约变化
   ```

   #### C1 — Bounded

   ```text
   跨文件或涉及多个已知消费者
   边界和职责清楚
   状态和契约影响已知且可控
   ```

   #### C2 — Structural

   ```text
   跨模块职责或 seam 变化
   状态迁移
   公共或外部契约影响
   高代价设计决定
   多个工作包需要整合
   ```

2. **识别消费者。** 修改任何被消费的接口前，找出受影响方：
   - 静态引用（调用、导入、类型使用）；
   - 动态或隐式消费者（配置、序列化格式、事件、外部系统）；
   - 状态消费者（读取相关数据的代码和流程）。

   控制范围内的内部生产者和消费者一起更新，不留半新半旧的过渡层。
   发现消费者超出当前控制范围（已发布 API、外部系统、必须保留的状态）时，
   这是契约或状态影响，按 `policy/decision-boundaries.md` 处理，
   必要时经 `align-work` 确认。

3. **按等级匹配工作方式。**
   - C0：直接实现，压缩契约，局部验证即可；
   - C1：实现前确认边界和消费者清单，可按文件或模块委派工作包；
   - C2：先明确结构方向，按 seam 切分工作包，分别委派、最后整合；
     设计决定按"持续设计"和"结构判断"处理，不为假想未来建抽象。

4. **实现并收敛。** 遵循 `policy/working-contract.md` 的简单性、持续设计、
   开发收敛与兼容规则。一个变化收敛的标志是：一致完整的实现、
   无竞争的新旧设计、无临时 fallback 残留。

5. **重新定级。** 等级随真实发现调整：
   - 发现隐藏消费者、状态影响或跨模块耦合时升级，并按新等级补足
     边界确认、委派划分和验证计划；
   - 发现预想的影响不存在时降级，取消不再必要的仪式；
   - 定级变化是判断记录，不需要任何人批准——但它影响的契约或状态
     决策仍按决策边界处理。

6. **交棒。** 形成可验证的完整候选后，连同 Work Unit Contract、
   Changes 和已做验证一起交给 `finish-work`。

# Delegation

- C0 通常不委派，主 Agent 直接实现；
- C1 可按文件或模块把实现切给 worker，工作包格式见
  `skills/_shared/delegation-contract.md`，每个工作包写明
  Owned files or modules 和 Forbidden scope expansion；
- C2 按 seam 切分多个工作包并行或串行委派，主 Agent 负责整合，
  并亲自处理跨包的设计决定；
- 不得让多个 worker 同时修改同一文件或模块；
- worker 返回的 Result Envelope 中的 Unverified areas 必须在交棒给
  `finish-work` 前显式处理或转交。

# Output

- 可验证的候选结果：代码、配置、文档等工件变化；
- 更新后的 Work Unit Contract（消费者、契约影响、状态影响的实际情况）；
- Changes 摘要和已执行的验证记录；
- 明确的"候选可验证"交接，不包含最终状态判断。

# Completion and stop conditions

- 候选结果收敛、关键 Claims 可被验证：交棒给 `finish-work`，本 Skill 结束；
- 实现中发现目标或验收需要实质变化：经 `align-work` 处理后再继续；
- 发现的工作属于独立目标：创建新 work unit 或记录后移交，不在当前
  work unit 内扩张；
- 结构判断反复变动、无法收敛：停止实现，把设计分叉带回主 Agent
  重新判断，必要时经 `align-work` 对齐；无法继续时交给 `finish-work`
  判断（`BLOCKED` 或 `HANDOFF`），而不是继续 patch。

# Related policy and references

- `policy/working-contract.md` — 简单性与工程质量、持续设计、结构判断、
  开发收敛、兼容与迁移、检查时机、临时工具；
- `policy/decision-boundaries.md` — 自主与升级边界、范围变化处理；
- `skills/_shared/work-unit-contract.md` — Implementation extension 字段；
- `skills/_shared/delegation-contract.md` — 工作包与结果格式；
- `skills/_shared/work-lifecycle.md` — 执行在整个闭环中的位置。
