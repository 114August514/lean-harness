# Work Unit Contract

## 目的

Work Unit Contract 把一个工作单元的目标、边界和完成判断写成可以检查的事实陈述，
让主 Agent、worker 和 reviewer 对同一份工作有相同的理解。

它是工作开始时的最小对齐产物，也是 `verify-work`、`review-work` 和 `finish-work`
的共同输入。

本文件只定义契约的字段和语义。契约是一份文档，不是数据库 schema、JSON Schema
或持久化状态。

---

## 结构

```text
Base contract
+
Type-specific extension
```

一个 work unit 只有一个主类型（`implementation` / `debugging` / `investigation`），
只附加对应的一个 extension。

发现新的独立目标时，应创建新的 work unit，而不是让当前 work unit 无限扩张。

---

## Base Contract

```text
Type
Intended outcome
Deliverable
Acceptance criteria
Acceptance mode
Scope
Non-goals
Constraints
Assumptions
Claims
Primary risks
```

| 字段 | 含义 |
| --- | --- |
| Type | 主类型：`implementation` / `debugging` / `investigation` |
| Intended outcome | 工作完成后应当成立的业务或工程结果，一句话即可 |
| Deliverable | 交付物的具体形态：代码变化、文档、诊断结论、评估报告等 |
| Acceptance criteria | 判断 Intended outcome 是否成立的检查条件 |
| Acceptance mode | `objective` / `subjective` / `mixed`，见下文 |

`Acceptance criteria` 的客观部分应被拆解为具体 Claims；
`verify-work` 的验证对象统一为 Claims，`Acceptance criteria` 仅用于
总体验收层面的汇总判断。
| Scope | 允许触碰的边界：文件、模块、系统、数据 |
| Non-goals | 明确不在本次范围内的内容，防止扩张 |
| Constraints | 不可违反的限制：兼容义务、性能上限、禁止事项 |
| Assumptions | 尚未证实但按其为真推进的前提；每条假设都应可被验证推翻 |
| Claims | 关键的可验证陈述，是 `verify-work` 的验证对象 |
| Primary risks | 最可能让结果无效或造成损失的两三个风险 |

### Claims

Claim 是对当前工作的可验证陈述，例如"修改后导出接口返回相同数据"、
"故障由连接池耗尽导致"、"方案 B 在目标负载下更快"。

- Claim 必须能绑定到具体工件、数据或行为；
- 每个 Claim 至少能被一种 Evidence action 支持或反驳；
- 只记录对完成判断有实质影响的 Claim，穷举所有可验证事实不是目标。

### Acceptance mode

验收方式在契约建立时确定，并被对齐、验证和最终完成判断实际使用。

```text
objective
subjective
mixed
```

#### objective

验收可以通过明确规则、命令、测试、测量结果或既定 rubric 判断。

#### subjective

验收依赖产品、体验、语气、视觉、审美或其他人类判断。必须记录：

```text
Human confirmation required
What must be confirmed
```

尚未获得人类确认时，不应立即停止工作。应先完成所有仍可独立、安全完成的
实现、客观验证和评审准备。最终是 `DONE`、`BLOCKED` 还是 `HANDOFF`，
由 `finish-work` 在完成阶段判断。

#### mixed

分别记录客观部分和主观部分。两部分均满足后才能 `DONE`；
主观部分的处理与 subjective 相同。

---

## Type-specific extensions

### Implementation extension

```text
Goal
Affected consumers
Contract impact
State impact
Development level
```

| 字段 | 含义 |
| --- | --- |
| Goal | 要实现的持久变化，可与其他字段相互引用而不必重复展开 |
| Affected consumers | 受影响的调用方、使用者或下游系统 |
| Contract impact | 是否改变 public API、模块契约或跨系统协议 |
| State impact | 是否涉及必须保留或迁移的数据、配置、外部状态 |
| Development level | 初始 C0 / C1 / C2 判断，见 `implement-change` |

### Debugging extension

```text
Observed symptom
Expected behavior
Reproduction status
Diagnostic depth
Incident mode
```

| 字段 | 含义 |
| --- | --- |
| Observed symptom | 可观察到的异常现象，尽量带原始报错或现象描述 |
| Expected behavior | 正常时应有的行为 |
| Reproduction status | 稳定复现 / 间歇复现 / 尚未复现 |
| Diagnostic depth | 初始 D0 / D1 / D2 判断，见 `debug-problem` |
| Incident mode | 是否处于 incident 模式，见 `debug-problem` 的 `incident-mode.md` |

### Investigation extension

```text
Intent
Question or exploration objective
Decision supported
Search space
Baseline or comparison frame
Evidence standard
Validity threats
Exit criteria
Investigation level
```

| 字段 | 含义 |
| --- | --- |
| Intent | `Explore` / `Evaluate` / `Test`，见 `investigate-question` |
| Question or exploration objective | 要回答的问题或要探索的目标 |
| Decision supported | 本次调查支撑什么后续决定 |
| Search space | 考虑的候选范围及其边界 |
| Baseline or comparison frame | 比较基准或对照系，Evaluate / Test 通常必填 |
| Evidence standard | 结论需要达到的证据强度 |
| Validity threats | 最可能让结论失效的因素（测量噪声、环境差异、样本偏差等） |
| Exit criteria | 什么条件下可以停止调查 |
| Investigation level | 初始 I0 / I1 / I2 判断，见 `investigate-question` |

---

## 压缩表达

不得强制所有工作填写同一套完整模板。

低强度工作（如 C0 局部修改、D0 直接修复、I0 快速探针）可以使用压缩形式：

- 无内容的字段直接省略，而不是填写"无"；
- 一句话能说明的字段不写段落；
- 压缩后的契约仍必须能让人回答：做什么、做到什么程度算完成、边界在哪里。

高强度工作（C2、D2、I2、incident、主观验收、高代价决定）应保留完整契约，
并显式记录 Claims、Primary risks 和相应的 extension 字段。

---

## 不属于本契约的内容

Work Unit Contract 不定义、也不应演化为：

- JSON Schema 或任何机器可校验的 schema；
- 持久化状态或数据库字段；
- workflow ID、任务队列条目或事件日志格式；
- 状态迁移表。

契约随工作单元存在，工作单元结束时它的使命即完成。
长期需要保留的结论进入代码、文档或决策记录，而不是留在契约里。

---

## 与其他文件的关系

- 职责顺序和完成规则：`skills/_shared/work-lifecycle.md`
- 主 Agent 与 worker 之间的交接格式：`skills/_shared/delegation-contract.md`
- 自主性、测试与验证、完成语义等一般规则以 `policy/` 为准，本文件不复述。
