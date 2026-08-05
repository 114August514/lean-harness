# Work Lifecycle

## 目的

本文件定义一个工作单元从开始到结束的责任顺序：每个环节由谁负责、
产物交给谁、出问题往哪里走。

它是方法语义，不是可执行流程定义。这里没有 gate、transition table
或生命周期状态机，执行顺序允许按实际情况跳跃和重入——例如简单工作
可以跳过委派，发现新症状可以回到诊断。

---

## 责任顺序

```text
align when needed
→ execute
→ verify
→ review
→ bounded remediation when needed
→ reverify affected claims
→ targeted re-review when needed
→ finish
```

| 环节 | 负责 Skill | 产物 |
| --- | --- | --- |
| align when needed | `align-work` | 语义对齐结果，或明确记录的自主决定 |
| execute | `implement-change` / `debug-problem` / `investigate-question` | 可验证的候选结果 |
| verify | `verify-work` | 每个关键 Claim 的 `PASS` / `FAIL` / `INSUFFICIENT` |
| review | `review-work` | `PASS` / `FINDINGS` |
| bounded remediation when needed | 由 `finish-work` 委派执行 worker | 修复后的工件 |
| reverify affected claims | `verify-work` | 受影响 Claim 的新 Evidence |
| targeted re-review when needed | `review-work` | `PASS` / `FINDINGS` |
| finish | `finish-work` | `DONE` / `BLOCKED` / `HANDOFF` |

三个执行 Skill 是并列入口，按 work unit 的主类型选择其一。
执行 Skill 形成候选结果后即交给 `finish-work`，不自行宣称完成。

`align-work` 在三个时机按需出现：工作开始时、执行中发现实质语义分叉时、
完成前需要人类验收时。它处理对齐，不启动完整闭环。

---

## 必要规则

### 验证词汇

`verify-work` 对每个关键 Claim 只输出三个 verdict：

```text
PASS
FAIL
INSUFFICIENT
```

- `PASS`：Evidence 支持该 Claim；
- `FAIL`：Evidence 充分，但反驳该 Claim 或表明 Acceptance 未满足；
- `INSUFFICIENT`：当前 Evidence 不足以得出可靠判断。

`FAIL` 和 `INSUFFICIENT` 不得互相伪装：反驳性证据不是证据不足，
证据缺口也不是 Claim 失败。

### Remediation 使旧 Evidence 失效

Remediation 是对 Delegation Contract Work Package 的特化，在通用字段之上
固定以下内容：

```text
Reason               修复原因：Claim failed / Acceptance failed /
                     Evidence insufficient / Review finding
Required outcome     什么结果出现算修复完成
Allowed scope        允许修改的范围，不得扩大
Affected claims      受影响的 Claims
Required verification 修复后必须重新验证的内容
```

任何 remediation 修改了可能影响 Claim 的工件后：

```text
识别受影响 Claims
→ 使相关旧 Evidence 失效
→ 先重新验证这些 Claims
→ 再进行 targeted re-review
```

只有能说明修改与该 Claim 无关时，旧 Evidence 才继续有效。
不得在未重新验证的情况下用旧 Evidence 支撑修改后的工件。

### Targeted re-review 的最低覆盖

修复后的 targeted re-review 至少覆盖：

```text
修复内容
直接消费者
受影响 Claims
相关 Review axes
因修改而失效的先前结论
```

不要求机械重跑完整 review，但也不允许只检查改动的那几行。

### 最终状态的唯一出口

所有最终状态由 `finish-work` 输出，只使用：

```text
DONE
BLOCKED
HANDOFF
```

其他 Skill 可以形成结论、建议和证据，但不得自行宣称最终状态；
遇到无法继续的情况时，把未解决依赖连同现状交给 `finish-work` 判断。

### Remediation 有边界且不无限循环

Remediation 使用上述特化工作包，不得借修复之名
堆积补丁或扩大范围。同一 material Finding 反复修复仍无实质进展，
或作用范围明显扩大时，停止局部循环，由 `finish-work` 重新判断
（重新设计、新 work unit、`BLOCKED` 或 `HANDOFF`）。

---

## 这不是什么

本文件不定义、也不应演化为：

- 持久状态机或状态迁移表；
- gate 或准入准出检查点体系；
- DAG、任务调度或自动流转；
- 可由机器执行或校验的流程定义。

环节之间的推进由主 Agent 根据当前实际情况判断，唯一被固定下来的是
责任归属和上述必要规则。

---

## 与其他文件的关系

- 工作单元的目标与验收格式：`skills/_shared/work-unit-contract.md`
- 主 Agent 与 worker 之间的交接格式：`skills/_shared/delegation-contract.md`
- 最终状态的具体语义以 `policy/working-contract.md` 的"完成语义"为准。
