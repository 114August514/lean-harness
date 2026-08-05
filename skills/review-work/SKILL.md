---
name: review-work
description: 从实现者之外的审查视角检查工作结果，按风险选择 self / fresh-context / independent 模式，输出 PASS 或 FINDINGS。不修改工件，不重启完整流程。
---

# Purpose

以与实现过程分离的审查视角检查工作结果，发现验证难以覆盖的问题：
结构错位、设计风险、推理漏洞、与目标脱节。

`review-work` 只负责审查和输出 Finding。它不修改工件、不执行 remediation、
不重启完整流程——这些由 `finish-work` 编排。

# Use when

- 候选结果通过验证后，需要独立视角的审查；
- remediation 后需要 targeted re-review；
- 工作的风险等级要求比自我检查更强的审查。

# Do not use when

- 候选结果尚未通过验证——先 `verify-work`，不要把 review 当验证用；
- 只需要确认 Claim 是否有证据——那是 `verify-work`；
- 极低风险工作已完成 self-review 且验证充分——不重复 review。

# Inputs

- Work Unit Contract（Intended outcome、Acceptance criteria、Claims、
  Acceptance mode）；
- 候选结果：Changes 摘要、Evidence 记录、`verify-work` 的 verdict；
- 审查材料本身（代码 diff、调查数据、诊断结论），而非实现者的完整叙事。

# Process

1. **选择 Review axes。** 按 work unit 主类型选择审查维度：

   Implementation：

   ```text
   Correctness   实现是否做了契约要求的事
   Structure     结构是否归属正确、无临时残留
   Outcome       是否真正达成 Intended outcome
   Alignment     是否与目标、验收和人类决定一致
   ```

   Debugging：

   ```text
   Diagnosis     根因结论是否被证据支撑
   Fix           修复是否针对根因而非症状
   Regression    是否引入或暴露了相邻问题
   Outcome       原始症状是否真正消除
   ```

   Investigation：

   ```text
   Method            方法是否与 Level 匹配
   Evidence          证据是否支撑结论强度
   Inference         从证据到结论的推理是否成立
   Decision relevance 结果是否真正支撑 Decision supported
   ```

2. **选择 Review mode。** 模式是风险匹配的执行选择，不是持久状态：

   ```text
   self            仅用于极低风险、机械、客观且验证直接的工作
   fresh-context   用于普通工作；新上下文中执行，只提供审查材料
   independent     用于高风险工作
   ```

   高风险工作包括：Incident；安全、权限或隐私；保留数据或状态迁移；
   公共或外部契约；生产或共享状态；关键并发或分布式行为；
   支撑高代价决定的 Investigation。

   模式不可用时，将保障缺失本身作为 Finding 输出：

   - 高风险工作无法获得 independent review：输出 `FINDINGS`，包含
     `BLOCKER: required review assurance unavailable`，由 `finish-work`
     判断 `BLOCKED` 或 `HANDOFF`；
   - 普通工作无法获得 fresh context：进行明确标记的 self-review，
     并加强客观验证；不得将其描述为 independent review；
   - 审查材料不足以支撑判断：输出 `FINDINGS`，包含
     `IMPORTANT` 或 `BLOCKER: insufficient review material`，
     说明缺口，不猜测下结论。

3. **执行审查。** 围绕 axes 检查审查材料。审查依据是契约和材料本身，
   不是实现者的解释——实现叙事会引导审查者重走实现者的盲区。

   对 targeted re-review，除相关 axes 外必须检查：因修复而失效的
   先前结论是否已被重新验证、更新或明确标记为不再有效。

4. **输出。** 只输出两种结论：

   ```text
   PASS
   FINDINGS
   ```

   每个 Finding 包含：

   ```text
   Severity                 BLOCKER / IMPORTANT / OPTIONAL
   Evidence                 支撑该 Finding 的具体材料位置或观测
   Affected claim or outcome
   Required outcome         什么结果出现才算该 Finding 被处理
   Scope impact             该 Finding 是否意味着范围变化
   ```

5. **范围扩大作为 Finding 属性处理。** 审查发现工作超出原契约范围、
   或需要超出原范围才能正确完成时，不增设特殊顶层输出，而是在
   Finding 的 Scope impact 中说明：

   - 仍服务相同目标且范围受控：主 Agent 自主整合；
   - 改变目标、验收或产品语义：经 `align-work` 对齐；
   - 属于独立目标：建议创建新 work unit 或 `HANDOFF`。

# Delegation

- fresh-context 和 independent review 的执行者必须与实现隔离：
  只接收审查材料，不接收实现过程叙事；
- self-review 由实现者自查，仅适用于上面限定的极低风险场景；
- 多个 review 视角（不同 axis 或不同审查者）可以并行委派，
  主 Agent 负责合并 Finding 并去重。

# Output

```text
PASS
或
FINDINGS（每条含 Severity / Evidence / Affected claim or outcome /
Required outcome / Scope impact）
```

并附：使用的 Review mode 及与实际风险的匹配说明；模式降级时的
明确标注。

# Completion and stop conditions

- 审查覆盖全部相关 axes 并输出结论：结束；
- Finding 已写明 Required outcome 即视为表达完整，不附带修复实现；
- 材料不足或模式不可用等保障缺失已通过 Finding 表达：结束。

# Related policy and references

- `policy/working-contract.md` — 检查时机、完成语义；
- `skills/_shared/work-unit-contract.md` — 契约字段；
- `skills/_shared/work-lifecycle.md` — review 与 targeted re-review 的位置；
- `skills/verify-work/SKILL.md` — review 与 verify 的分工。
