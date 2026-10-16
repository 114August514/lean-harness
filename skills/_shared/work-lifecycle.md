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

| 环节 | 对应阶段 | 负责 Skill | 核心产物与命令 |
| --- | --- | --- | --- |
| align when needed | **Stage 1 & 2** (意图/契约) | `align-work` | 目标与非目标 (Non-goals)，或结构契约 |
| execute | **Stage 4** (切片实现) | `implement-change` / `debug-problem` / `investigate-question` | 先红后绿的测试与生产代码 (Worktree 隔离) |
| verify | **Stage 4** (自愈与检验) | `verify-work` | 执行 `make check`，输出每个 Claim 的 `PASS` / `FAIL` |
| review | **Stage 5** (机械审计) | `review-work` | 运行 `make audit`，输出 `PASS` / `FINDINGS` |
| bounded remediation | **Stage 4** (自主纠错) | 由 `finish-work` 委派执行 worker | 基于 Traceback 自主修复的工件 |
| reverify | **Stage 4** (复验) | `verify-work` | 重新运行 `make check` |
| targeted re-review | **Stage 5** (复核) | `review-work` | 仅复核受影响代码的 Git Diff |
| finish | **Stage 5** (差量交付) | `finish-work` | `DONE` (合入并清理 Worktree) / `BLOCKED` |

三个执行 Skill 是并列入口，按 work unit 的主类型选择其一。
执行 Skill 形成候选结果后即交给 `finish-work`，不自行宣称完成。
详细五阶段设计与双轨分流见 `workflow/lifecycle.md`。

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

## 与连续性的关系

工作连续性（检查点、恢复日志、工作日志、上下文恢复）的权威定义见
`continuity/contract.md`。本文件只规定 Skills 在生命周期中何时与连续性组件交互，
不复述其语义。

- 执行 Skill 在形成可验证候选结果时，应确保当前 intent 已记录，
  结果不透明的外部操作已有 `begin / end`；
- `finish-work` 在输出最终状态前，按 `continuity/contract.md` 的
  “Skills、完成检查与 Git 最小不变量”
  检查恢复日志和检查点状态；
- worker 与主 Agent 之间的候选工作事件交接，见
  `skills/_shared/delegation-contract.md`。

Git 的实际开发流程、branch / worktree 使用、cleanup、事实保真和机械不变量统一以
`substrates/git/contract.md` 为权威来源。Skills 决定何时、为何以及采用什么 Git 操作，并通过
Bash 调用原生 Git，不依赖 Local Git MCP。

---

## 与其他文件的关系

- 工作单元的目标与验收格式：`skills/_shared/work-unit-contract.md`
- 主 Agent 与 worker 之间的交接格式：`skills/_shared/delegation-contract.md`
- 工作连续性（检查点、恢复日志、工作日志）的权威定义：`continuity/contract.md`
- Git 工作流程与机械不变量：`substrates/git/contract.md`
- 最终状态的具体语义以 `policy/working-contract.md` 的"完成语义"为准。
