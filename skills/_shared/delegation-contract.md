# Delegation Contract

## 目的

Delegation Contract 定义主 Agent 与 worker 之间交接工作的最小格式。

worker 指在与主 Agent 隔离的上下文中执行边界明确工作的执行者。它可以是
subagent，也可以是主 Agent 在新上下文中开启的一段工作。本契约只规定交接的
语义内容，不规定任何 Runtime 的调用语法。

---

## Work Package

主 Agent 交给 worker 的工作包至少包含：

```text
Goal
Scope
Fixed facts
Questions
Constraints
Allowed actions
Expected output
```

| 字段 | 含义 |
| --- | --- |
| Goal | 这个工作包要达成什么，与 work unit 目标的关系 |
| Scope | 允许触碰的边界：文件、模块、系统 |
| Fixed facts | 已经确认、worker 不需要也不应重新调查的事实 |
| Questions | worker 需要回答的具体问题（调查类工作包） |
| Constraints | 不可违反的限制 |
| Allowed actions | worker 可以执行的动作范围，特别是允许修改什么 |
| Expected output | 期望的 Result Envelope 形态和重点 |

修改工件时按需增加：

```text
Owned files or modules
Forbidden scope expansion
Required verification
```

- **Owned files or modules**：该 worker 独占修改权的文件或模块。
- **Forbidden scope expansion**：明确禁止顺手处理的相邻问题。
- **Required verification**：交付前必须完成的最低验证。

当工作单元已接入工作连续性（`continuity/contract.md`）时，工作包按需携带：

```text
Work reference            关联的 Issue / Work Unit
Cycle id                  当前处理周期
Starting commit / checkpoint
Owned worktree            worker 独占的 worktree（及其恢复日志）
Relevant unresolved events 恢复时需要知道的未解决旧事件
```

工作包应自洽：worker 不应需要阅读主 Agent 的完整对话才能理解任务。
同时只放入完成该工作包所需的信息，不要把主上下文整个复制过去。

---

## Result Envelope

worker 返回的结果至少包含：

```text
Result
Evidence
Changes
Verification
Assumptions
Unresolved
```

| 字段 | 含义 |
| --- | --- |
| Result | 压缩后的结论或交付摘要，不是过程记录 |
| Evidence | 支撑 Result 的关键证据及其获得方式 |
| Changes | 做了什么变化（调查类工作包可为"无") |
| Verification | 已执行的验证及结果 |
| Assumptions | worker 作出的、主 Agent 需要知道的假设 |
| Unresolved | 未能解决、需要主 Agent 决定或继续处理的事项 |

涉及代码或工件修改时增加：

```text
Changed files
Commands run
Observed results
Unverified areas
```

- **Changed files**：实际修改的文件清单。
- **Commands run**：执行过的关键命令。
- **Observed results**：命令和验证的实际输出要点。
- **Unverified areas**：修改了但没有验证到的区域，必须如实列出。

当工作单元已接入工作连续性（`continuity/contract.md`）时，worker 返回还应包含：

```text
Resulting commits           产生的 commit
Candidate work events       候选工作事件（是否进入长期工作日志由主 Agent 决定）
Open or unknown operations  未结束或结果未知的操作（begin 无 end）
```

worker 不直接写 Project 工作日志的长期分区；候选事件交回主 Agent 检查后追加
（写入所有权见 `continuity/contract.md` 的“写入所有权与正式决定”）。

---

## 所有权与边界

- 一个文件或模块在同一时刻只有一个 worker 拥有修改权；
- 不得让多个 worker 在没有明确所有权划分的情况下并行修改相同文件或模块；
- worker 不得超出 Owned files or modules 修改其他内容；发现边界外的问题时，
  记录进 Unresolved 交回主 Agent，而不是顺手修改；
- worker 返回 Evidence 和 Unverified areas 是义务，不是可选项；没有验证的区域
  必须显式标注，不允许用"应该没问题"带过。

---

## 主 Agent 的吸收方式

主 Agent 只把压缩后的结论、决策和 Evidence 吸收进主上下文：

- 保留 Result、Evidence 要点、Changes、Unresolved；
- 不默认把 worker 的完整调查轨迹、中间尝试和原始日志带入主上下文；
- 需要复核细节时，重新按需获取，而不是预先囤积。

委派是为了获得隔离上下文中的专注执行和上下文压缩，不是为了形式上
"把任务分出去"。边界不清、无法自洽描述的工作，应先由主 Agent 收敛出
可交接的工作包再委派。

---

## 不属于本契约的内容

本契约不定义、也不应演化为：

- 任何具体 Runtime 的 subagent 调用语法或参数格式；
- 任务队列条目、worker 注册表或调度协议；
- worker 的持久身份或跨会话恢复机制；
- 自动重试、超时退避或失败转移策略。

这些属于未来可能存在的 Runtime Adapter 的职责。

---

## 与其他文件的关系

- 工作单元的目标与验收格式：`skills/_shared/work-unit-contract.md`
- 委派在整个闭环中的位置：`skills/_shared/work-lifecycle.md`
- 连续性相关字段的语义：`continuity/contract.md` 的
  “Skills、完成检查与 Git 最小不变量”
