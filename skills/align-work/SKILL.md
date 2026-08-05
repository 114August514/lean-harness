---
name: align-work
description: 在工作开始、执行中发现实质语义分叉、或完成前需要人类确认时，用最低沟通成本与人类对齐目标、验收或产品语义。技术不确定性不属于本 Skill；局部可逆的实现选择应记录假设后继续。
---

# Purpose

识别会实质改变最终结果的语义分叉，并用最低沟通成本与人类对齐。

`align-work` 保护的是"人类负责语义"这条边界。它处理对齐，不启动完整闭环，
不代替执行 Skill 做实现、诊断或调查。

# Use when

- 工作开始时，目标、验收或范围存在实质语义不清；
- 执行中发现会改变最终结果的分叉（用户可见行为、产品语义、验收含义）；
- 完成前，Acceptance mode 为 subjective 或 mixed，需要人类确认；
- Review 或 remediation 揭示了改变目标、验收或范围的变化。

# Do not use when

- 只是技术事实未确定——用调查、实验或验证去确定它；
- 只是局部、低成本、可逆的实现选择——记录假设后继续（见
  `policy/decision-boundaries.md` 的"默认决策规则"和"不确定性处理"）；
- 只是需要一个可以自主作出的工程判断——不要把它包装成人类决策；
- 工作没有实质语义分叉——`align-work` 不是默认审批入口，也不是开工仪式。

# Inputs

- Work Unit Contract（已有部分，可为草稿）；
- 已确认的事实和当前理解；
- 触发对齐的具体分叉。

# Process

1. **判断是否真需要问人类。** 按下表分流：

   ```text
   技术事实可以确定
   → Agent 自主处理，不提问

   局部、低成本、可逆
   → 记录假设后继续推进

   由人类偏好、产品语义或业务权衡决定
   → 提问，但先推进不受该分叉影响的工作

   涉及外部契约、保留状态、安全或不可逆操作
   → 提问并等待答复后再触碰受影响部分
   ```

   具体边界以 `policy/decision-boundaries.md` 为准，本 Skill 不复述也不扩大。

2. **检查 Acceptance mode。**
   - objective：语义分叉消除后即可继续，无需人类参与验收；
   - subjective / mixed：记录 `Human confirmation required` 和
     `What must be confirmed`，然后继续完成所有仍可独立、安全完成的
     客观工作，不因等待确认而提前停摆。

3. **构造提问。** 每个问题包含：

   ```text
   当前理解
   未解决的分叉
   具体选项及后果
   Agent 建议
   ```

   一次提问合并相关的分叉，避免用一串碎问题打断人类。

4. **回写结果。** 把对齐结论（或自主决定及其依据）更新进
   Work Unit Contract，并标记哪些工作曾因此暂停、现在可以继续。

# Delegation

`align-work` 通常由主 Agent 直接执行，不委派给 worker。
语义对齐需要主上下文中的目标和契约，隔离上下文反而削弱它。

# Output

- 更新后的 Work Unit Contract（含对齐结论或记录的假设）；
- 给人类的紧凑提问（如需），附建议与选项后果；
- 明确标记：哪些工作可以继续，哪些必须等待。

# Completion and stop conditions

- 分叉被消除，或确认不存在实质分叉、无需提问：结束；
- 提问后人类答复：回写契约，结束；
- 提问后无答复且没有可独立推进的工作：把未解决依赖交给
  `finish-work` 判断，不要无限等待或反复追问同一问题。

# Related policy and references

- `policy/decision-boundaries.md` — 自主与升级的完整规则；
- `policy/working-contract.md` — 完成语义、BLOCKED 判定；
- `skills/_shared/work-unit-contract.md` — Acceptance mode 的字段语义；
- `skills/_shared/work-lifecycle.md` — 对齐在整个闭环中的位置。
