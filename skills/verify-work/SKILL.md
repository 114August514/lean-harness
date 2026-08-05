---
name: verify-work
description: 为关键 Claim 和 Acceptance criteria 选择并执行最低成本的充分 Evidence，对每个 Claim 输出 PASS / FAIL / INSUFFICIENT。不自动调用 Review 或 Finish，不代替测试策略。
---

# Purpose

为关键 Claim 和 Acceptance criteria 选择并执行最低成本的充分 Evidence，
把"应该没问题"变成可检查的判断。

`verify-work` 只负责产生 Evidence 和 verdict。它不自动调用 Review，
不启动 remediation，不输出最终状态——这些属于 `finish-work`。

# Use when

- 执行 Skill 交付了候选结果，需要验证关键 Claims；
- remediation 修改了工件，需要重新验证受影响 Claims；
- Acceptance criteria 的客观部分需要证据；
- 任何时候完成判断缺乏 fresh evidence。

# Do not use when

- 还没有可验证的候选结果或明确 Claim——先回到执行 Skill；
- 需要的是实现者之外的审查视角——那是 `review-work`；
- 只是想"多跑点测试更安心"——验证由 Claim 和风险驱动，
  不由焦虑驱动（见 `policy/working-contract.md` 的"检查时机"）。

# Inputs

- Work Unit Contract（Claims、Acceptance criteria、Acceptance mode）；
- 候选结果及其 Changes 摘要；
- remediation 时：受影响 Claims 清单和已失效的旧 Evidence。

# Process

1. **确定验证对象。** 从契约中取出关键 Claims 和 Acceptance criteria 的
   客观部分。没有写入契约但对新出现风险必要的 Claim，补充进契约再验证。

2. **为每个 Claim 选择最低成本的充分 Evidence。** Evidence 的形式由
   Claim 和风险决定：

   ```text
   自动化测试（已有或新增）
   命令执行与输出检查
   构建、类型检查、lint
   手工或脚本化操作验证
   测量与 benchmark 数据
   日志、监控、trace 观测
   文档与代码的交叉核对
   ```

   不把 Evidence 等同于自动化测试，也不默认新增永久测试——是否保留
   测试按 `policy/working-contract.md` 的"测试与验证"判断。

3. **执行并记录。** 每条 Evidence 至少记录：

   ```text
   Claim
   Subject snapshot（被验证的工件、数据或结果的标识：版本、commit、路径等）
   Evidence action
   Observed result
   Validity scope（该证据在什么条件下有效）
   Known gaps
   ```

   环境敏感时按需补充：Environment、Configuration、
   Dependency or data version、Parameters。

4. **给出 verdict。** 每个 Claim 恰好一个：

   ```text
   PASS           Evidence 支持该 Claim
   FAIL           Evidence 充分，但反驳该 Claim 或表明 Acceptance 未满足
   INSUFFICIENT   当前 Evidence 不足以得出可靠判断
   ```

   严格区分 FAIL 与 INSUFFICIENT：反驳性证据不是证据不足，
   证据缺口也不是 Claim 失败。

5. **给出覆盖说明。** 汇总 Claims checked、Coverage rationale、
   Remaining gaps，连同 verdict 一起输出。

# Delegation

- 验证执行（跑命令、做测量、核对文档）适合委派给 worker，工作包写明
  要验证的 Claims、允许的验证手段和 Expected output；
- verdict 判断可以由 worker 给出建议，但主 Agent 对 verdict 与 Claim、
  契约的一致性负责；
- remediation 后的 reverify 只针对受影响 Claims，不机械重跑全部验证。

# Output

```text
Claims checked
Evidence executed（每条含最小 Evidence Record）
Observed results
Subject snapshot
Coverage rationale（为什么这些证据足够覆盖这些 Claims）
Remaining gaps
```

每个 Claim 一个 verdict：`PASS` / `FAIL` / `INSUFFICIENT`。

# Completion and stop conditions

- 所有关键 Claims 都有 verdict，且每个 verdict 有对应 Evidence 支撑：
  输出结果，结束；
- 某个 Claim 当前环境无法获得充分 Evidence：verdict 记 `INSUFFICIENT`
  并在 Remaining gaps 说明，不为了得出判断而弱化证据标准；
- 验证执行暴露新的异常行为：记录并交回主 Agent，由主 Agent 决定
  是否转入 `debug-problem`，`verify-work` 不顺手修复。

# Related policy and references

- `policy/working-contract.md` — 测试与验证、检查时机、完成语义；
- `policy/decision-boundaries.md` — 测试与验证决策；
- `skills/_shared/work-unit-contract.md` — Claims 与 Acceptance mode 的语义；
- `skills/_shared/work-lifecycle.md` — 验证、reverify 在闭环中的位置。
