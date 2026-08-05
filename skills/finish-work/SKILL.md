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

- 候选结果尚未形成——回到相应执行 Skill；
- 只需要一次验证或一次 review 的中间判断——直接用 `verify-work`
  或 `review-work`，不经过完整编排。

# Inputs

- Work Unit Contract 及其 Claims、Acceptance criteria、Acceptance mode；
- 候选结果及 Changes 摘要；
- 执行阶段已有的验证和审查记录。

# Process

1. **编排验证。** 调用 `verify-work` 验证关键 Claims 和 Acceptance criteria
   的客观部分，按 verdict 分流：

   ```text
   PASS
   → 进入 Review

   FAIL
   → 构造 Remediation Package，委派修复

   INSUFFICIENT
   → 补充 Evidence；当前环境无法补充时，记录缺口，
     判断 BLOCKED 或 HANDOFF，不弱化证据标准强行通过
   ```

2. **编排审查。** 验证通过后调用 `review-work`，由其按风险选择
   self / fresh-context / independent 模式。确认模式与实际风险匹配；
   高风险工作无法获得 independent review 时，不得宣称 `DONE`，
   进入 `BLOCKED` 或 `HANDOFF`。

   仅当工作为 C0 / D0 / I0 等极低风险、验证已充分、且实现者已完成
   self-review 时，可以不再单独调用 `review-work`，但必须在最终判断中
   如实记录 review 强度为 self-review，不得描述为更高强度的审查。

3. **处理 Finding。** 每个 material Finding（BLOCKER / IMPORTANT）
   必须被以下方式之一处理：

   ```text
   修复
   以 Evidence 反驳
   由有权 authority 接受风险
   转交为明确的 HANDOFF
   ```

   OPTIONAL 默认不扩大当前范围，记录即可。范围变化按 Finding 的
   Scope impact 处理：同目标受控则自主整合；改变目标或验收则
   `align-work`；独立目标则新 work unit 或 `HANDOFF`。

4. **构造 Remediation Package。** 所有修复都以对
   `skills/_shared/delegation-contract.md` Work Package 特化的形式委派，
   在通用字段之上固定：

   ```text
   Reason               Claim failed / Acceptance failed /
                        Evidence insufficient / Review finding
   Required outcome     什么结果出现算修复完成
   Allowed scope        允许修改的范围
   Affected claims      受影响的 Claims
   Required verification 修复后必须重新验证的内容
   ```

   字段对应关系：`Reason` 写入 `Fixed facts` 作为修复背景；
   `Required outcome` 对应 `Goal` 与 `Expected output`；
   `Allowed scope` 对应 `Scope`、`Allowed actions` 与
   `Forbidden scope expansion`；`Affected claims` 不写入 `Fixed facts`，
   直接作为 `Required verification` 的输入；`Required verification` 同名保留。

   委派修复时按修复性质选择执行路径：代码改动按 `implement-change`、
   异常行为修复按 `debug-problem`、结论或数据修正按 `investigate-question`，
   并要求 worker 返回符合 Result Envelope 的 `Changes`、`Verification`、
   `Evidence` 与 `Unresolved`。

5. **Reverify。** 修复返回后：

   ```text
   识别受影响 Claims
   → 使相关旧 Evidence 失效
   → 重新验证这些 Claims
   ```

   能说明修改与某 Claim 无关时，其旧 Evidence 继续有效。
   不机械重跑全部检查。

6. **Targeted re-review。** 重新验证通过后进行，至少覆盖：

   ```text
   修复内容
   直接消费者
   受影响 Claims
   相关 Review axes
   因修改而失效的先前结论
   ```

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

9. **输出最终状态。** 只输出三个之一，语义以
   `policy/working-contract.md` 的"完成语义"为准：

   #### DONE

   只有同时满足：

   ```text
   Intended outcome 已实现
   Acceptance criteria 已满足
   必要的人类验收已完成
   关键 Evidence 对当前工件有效
   BLOCKER 和 IMPORTANT 已合法处理
   Review 强度与风险匹配
   不存在明显临时结构或未完成的重要行为
   ```

   #### BLOCKED

   仅当继续产生有效进展必须依赖缺失信息、权限、人类语义决定、
   外部环境或必要的高风险 Review，并且没有独立、安全的工作可以继续。
   执行 Skill 不直接宣称 `BLOCKED`，而是把未解决依赖交给本 Skill 判断。

   #### HANDOFF

   当前约定阶段已完成，后续工作由其他 owner、环境或 work unit 接手。
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
- `skills/_shared/delegation-contract.md` — remediation 委派的格式基础。
