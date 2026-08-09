---
name: finish-work
description: 唯一负责编排完成阶段并输出最终状态 DONE / BLOCKED / HANDOFF：编排 verify、review、bounded remediation、reverify 和 targeted re-review。不亲自修改工件。
---

# Purpose

把候选结果收敛为最终状态。`finish-work` 是完成阶段的唯一编排者：

```text
verify
→ review
→ bounded remediation when needed
→ reverify affected claims
→ targeted re-review
→ final status
```

这是责任顺序，不是状态机。`finish-work` 不亲自修改工件——修复由它
选择合适 worker 执行。

# Use when

- 执行 Skill（`implement-change` / `debug-problem` / `investigate-question`）
  交付了候选结果；
- 任何需要输出 `DONE` / `BLOCKED` / `HANDOFF` 的时刻。

# Do not use when

- 候选结果尚未形成，且仍有安全工作可以继续——回到相应执行 Skill；
- 只需要一次验证或一次 review 的中间判断——直接用 `verify-work`
  或 `review-work`，不经过完整编排。

# Inputs

- Work Unit Contract 及其 Claims、Acceptance criteria、Acceptance mode；
- 候选结果及 Changes 摘要（输出 `DONE` 时必需；输出 `BLOCKED` 或
  `HANDOFF` 时可为空）；
- 执行阶段已有的验证和审查记录。

# Process

1. **编排验证。** 调用 `verify-work` 验证关键 Claims 和 Acceptance criteria
   的客观部分，按 verdict 分流：

   ```text
   PASS
   → 进入 Review

   FAIL
   → 判断被反驳的 Claim 与 Intended outcome 的关系
     · 表明实现、修复或 Acceptance 未满足 → bounded remediation
     · 是 Investigation 对被测命题的有效反驳 → 作为调查结果进入 Review

   INSUFFICIENT
   → 补充 Evidence；当前环境无法补充时，记录缺口，
     判断 BLOCKED 或 HANDOFF，不弱化证据标准强行通过
   ```

2. **编排审查。** 验证通过后调用 `review-work`，由其按风险选择
   self / fresh-context / independent 模式。确认模式与实际风险匹配；
   高风险工作无法获得 independent review 时，不得宣称 `DONE`，
   进入 `BLOCKED` 或 `HANDOFF`。

   仅当整体风险极低、验证已充分、且实现者已完成 self-review 时，
   可以不再单独调用 `review-work`，但必须在最终判断中如实记录
   review 强度为 self-review，不得描述为更高强度的审查。
   C0 / D0 / I0 本身不构成低风险判定——Review mode 必须依据整体
   风险选择，例如 Incident + D0 仍属于高风险。

3. **处理 Finding。** 每个 material Finding（BLOCKER / IMPORTANT）
   必须被以下方式之一处理：

   ```text
   修复
   以 Evidence 反驳
   由有权 authority 接受风险
   转交为明确的 HANDOFF
   ```

   例外：`BLOCKER: required review assurance unavailable` 不得以
   "接受风险"方式处理，必须输出 `BLOCKED` 或 `HANDOFF`。

   OPTIONAL 默认不扩大当前范围，记录即可。范围变化按 Finding 的
   Scope impact 处理：同目标受控则自主整合；改变目标或验收则
   `align-work`；独立目标则新 work unit 或 `HANDOFF`。

4. **构造 Remediation Package。** 所有修复都以对
   `skills/_shared/delegation-contract.md` Work Package 特化的形式委派，
   字段和规则以 `skills/_shared/work-lifecycle.md` 的"必要规则"为准。

   Remediation worker 属于当前完成循环，不启动嵌套的 `finish-work`，
   也不默认创建新 work unit。它使用 `implement-change`、`debug-problem`
   或 `investigate-question` 的方法作为指导，直接把结果返回当前
   `finish-work`。只有范围已经变成独立目标时，才正式创建新 work unit。

5. **Reverify。** 修复返回后，识别受影响 Claims、使相关旧 Evidence
   失效、重新验证这些 Claims（规则见
   `skills/_shared/work-lifecycle.md`）。能说明修改与某 Claim 无关时，
   其旧 Evidence 继续有效。不机械重跑全部检查。

6. **Targeted re-review。** 重新验证通过后进行，覆盖范围以
   `skills/_shared/work-lifecycle.md` 的最低覆盖为准。
   输出仍是 `PASS` / `FINDINGS`。

7. **判断循环。** 同一 material Finding 反复修复仍无实质进展，
   或作用范围明显扩大时，停止局部循环，重新判断：

   - 是否需要完整重新设计；
   - 是否需要新的 work unit；
   - 是否 `BLOCKED`；
   - 是否 `HANDOFF`。

   不得无限循环。

8. **处理主观验收。** Acceptance mode 为 subjective / mixed 时，
   客观部分全部满足后，检查人类确认状态。若契约中尚未记录人类确认，
   先调用 `align-work` 构造提问并更新契约；`finish-work` 只根据契约中
   已记录的确认状态做判断，不直接发起人类提问：

   ```text
   已获得确认                         → 继续判断 DONE
   人类确认属于当前完成条件但未获得   → BLOCKED
   当前 deliverable 只需准备好供评审  → HANDOFF
   ```

   等待确认前应先完成所有仍可独立、安全完成的客观工作。

9. **连续性检查。** 当工作单元已接入工作连续性（`continuity/contract.md`）时，
   输出最终状态前确认：

   - 没有未解释的 `begin`（无 `end` 的外部操作已查询真实状态并处理）；
   - dirty working tree 已被理解：已 commit、已明确交接或已有下一步 intent；
   - 具有工作价值的 ignored / local-only artifact 已实际保留并显式交接，或已确认可重建；
   - 重要工件已经形成检查点，或未提交现场已明确交接；
   - 当前 Evidence 对应当前工件；
   - 具有长期价值的事件已经写入工作日志；
   - 具有约束力的决定没有只停留在日志中，已提升到 Issue / Spec / Policy / PR。

10. **输出最终状态。** 只输出三个之一：

   #### DONE

   语义以 `policy/working-contract.md` 的"完成语义"为准。在满足
   policy 定义的基础上，还要求本 Skill 编排的以下条件同时成立：

   ```text
   必要的人类验收已完成
   关键 Evidence 对当前工件有效
   BLOCKER 和 IMPORTANT 已合法处理
   Review 强度与风险匹配
   ```

   #### BLOCKED

   语义和判定以 `policy/working-contract.md` 的"完成语义"和
   `policy/decision-boundaries.md` 的"BLOCKED 判定"为准。
   执行 Skill 不直接宣称 `BLOCKED`，而是把未解决依赖交给本 Skill 判断。

   #### HANDOFF

   语义以 `policy/working-contract.md` 的"完成语义"为准。
   最小 HANDOFF 内容：

   ```text
   Completed
   Current state
   Reason for handoff
   Evidence still valid
   Remaining work
   Next owner or action
   Risks
   ```

   `Evidence still valid` 由主 Agent 根据 `verify-work` 输出的
   `Subject snapshot` 与 `Validity scope`，结合 remediation 后的工件状态
   综合判断，列出仍有效的证据清单。

# Delegation

- `finish-work` 编排但不亲自执行：验证委派给 `verify-work`，审查委派给
  `review-work`，修复委派给合适的执行 worker；
- remediation 工作包必须包含 Allowed scope，防止借修复扩大范围；
- worker 返回的 Unverified areas 必须在最终判断前显式处理。

# Output

最终状态三选一，附支撑材料：

```text
DONE     + 有效 Evidence 摘要、Review 结论、验收依据
BLOCKED  + 未解决依赖、已完成的独立工作、需要什么才能继续
HANDOFF  + 最小 HANDOFF 内容（见上）
```

# Completion and stop conditions

- 输出任一最终状态即结束；
- remediation 循环达到第 7 步的停止条件：停止循环并输出
  `BLOCKED` 或 `HANDOFF`，不继续局部修复；
- 发现完成所需的变化超出当前 work unit 目标：新 work unit 或
  `HANDOFF`，不在 finish 阶段静默扩张。

# Related policy and references

- `policy/working-contract.md` — 完成语义（DONE / BLOCKED / HANDOFF 的权威定义）；
- `policy/decision-boundaries.md` — BLOCKED 判定、请求人类决策的方式；
- `skills/_shared/work-lifecycle.md` — 责任顺序与必要规则；
- `skills/_shared/work-unit-contract.md` — Acceptance mode；
- `skills/_shared/delegation-contract.md` — remediation 委派的格式基础；
- `continuity/contract.md` — 完成阶段的连续性检查
  （“Skills、完成检查与 Git 最小不变量”）；
- `substrates/git/contract.md` — dirty worktree、commit reachability 与安全清理的机械不变量。
