---
name: debug-problem
description: 从可观察症状出发，以最低足够诊断深度解释并修复异常行为。按 D0/D1/D2 选择诊断深度；D2 时读取 systematic-diagnosis.md；涉及生产、数据、安全或重大可用性时按 incident-mode.md 先控制影响。
---

# Purpose

从症状出发，以最低足够诊断深度解释并修复异常行为。

`debug-problem` 负责诊断和修复的执行阶段。诊断深度是启发式选择，
不是流程状态；修复完成只表示"候选结果可验证"，完成判断属于
`finish-work`。

# Use when

- 存在可观察的异常行为、报错或故障症状；
- 需要解释"为什么会这样"并消除根因；
- 既有功能的行为与预期不符。

# Do not use when

- 没有异常症状，只是要实现新行为——用 `implement-change`；
- 目标是评估方案或回答开放问题——用 `investigate-question`；
- 症状根因和修复都已明确，只剩执行修改——直接按 `implement-change`
  的实现路径处理，不要套用诊断仪式。

# Inputs

- Work Unit Contract（含 Debugging extension：Observed symptom、
  Expected behavior、Reproduction status、Diagnostic depth、Incident mode）；
- 报错信息、日志、监控、用户报告等原始症状材料；
- 相关代码和近期变化。

# Process

1. **先判断是否为 Incident。** Incident 与 D0–D2 正交。出现生产、
   共享状态、数据、安全、隐私、资金或重大可用性影响时，读取
   `incident-mode.md`，按其要求先控制影响、保存证据、确认授权边界，
   然后仍以合适的 D 深度诊断。非 Incident 时跳过，不执行任何
   incident 仪式。

2. **选择 Diagnostic depth。**

   #### D0 — Direct Fix

   ```text
   根因明确
   因果路径直接
   修复局部且可逆
   原始症状可直接验证
   ```

   直接修复并验证原始症状。**D0 不进入假设流程**，不要为明显的问题
   编造假设清单。

   #### D1 — Hypothesis-driven

   ```text
   存在占优假设
   可以通过小型可逆实验验证
   ```

   用一个或少数几个小型可逆实验验证占优假设，确认后修复。

   #### D2 — Systematic Diagnosis

   ```text
   存在多个合理假设
   难复现或间歇发生
   涉及竞态、性能、环境或跨系统状态
   简单修复已经失败
   ```

   读取 `systematic-diagnosis.md`，按其中的系统化路径执行。

3. **按深度执行。** 共同约束：
   - 修复针对根因，不压制症状；
   - 验证以原始症状的消失为准，不以"代码看起来更合理"为准；
   - 调试用的临时 instrumentation、脚本、日志默认是施工工具，
     修复验证后清理，不随交付保留（规则见
     `policy/working-contract.md` 的"临时工具"）。

4. **升级与降级。** 深度随真实证据调整：
   - D0 修复后症状未消失、或 D1 占优假设被证伪且无新占优假设：升级；
   - D2 排查中根因变得明确：降级，直接修复；
   - 升级降级是诊断判断，不是状态迁移，不需要批准，但应记录依据。

5. **交棒。** 修复并初步验证后，把候选结果连同诊断结论、
   受影响 Claims 一起交给 `finish-work`。

# Delegation

- D0 通常由主 Agent 直接处理，不委派；
- D1 的实验和 D2 的定向观测适合委派给 worker，工作包写明要验证的
  假设、允许的观测手段和禁止修改的范围；
- Incident 中的影响控制动作（重启、回滚、限流等）未获授权不得委派
  执行，授权边界见 `incident-mode.md`；
- 委派格式见 `skills/_shared/delegation-contract.md`。

# Output

- 候选修复（工件变化）；
- 诊断结论：根因、因果路径、排除的假设；
- 原始症状的验证记录；
- 受影响 Claims 清单，供 `finish-work` 安排 reverify。

# Completion and stop conditions

- 根因确认、修复完成、原始症状可验证：交棒给 `finish-work`；
- 证据显示这不是一个 bug 而是需求或设计问题：经 `align-work` 确认后
  转为相应类型的 work unit；
- 合理深度内无法复现也无法取得有效观测：停止猜测式修改，记录已排除
  假设和剩余观测手段，交给 `finish-work` 判断（通常是 `BLOCKED` 或
  `HANDOFF`）；
- 同一区域反复修复失败：升级到更深诊断或停止，不无限试错。

# Related policy and references

- `skills/debug-problem/systematic-diagnosis.md` — D2 的系统化路径，按需读取；
- `skills/debug-problem/incident-mode.md` — Incident 处理，按需读取；
- `policy/working-contract.md` — 临时工具、检查时机；
- `policy/decision-boundaries.md` — 生产与外部操作边界；
- `skills/_shared/work-unit-contract.md` — Debugging extension 字段；
- `skills/_shared/work-lifecycle.md` — 诊断在整个闭环中的位置。
