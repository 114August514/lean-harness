# 工作连续性契约

## 目的

本文件是 Lean Harness 工作连续性能力的唯一权威契约。它定义：

- 各信息来源的职责；
- 两类日志（恢复日志、工作日志）的语义；
- Git 检查点；
- Project、Issue、cycle、PR 和 worktree 的关系；
- 当前状态与历史事件的组合方式；
- 上下文恢复算法；
- 存储和清理不变量。

本契约是 Runtime-neutral 的：它不绑定任何具体 Agent Runtime、存储引擎或传输方式。
本文件与参考实现同属 `continuity/` 目录；Skills 与本契约的接入点见
`skills/_shared/work-lifecycle.md`。

核心原则：

```text
模型上下文        → 可丢弃的运行信息
Issue / Spec      → 目标、范围、验收和正式决定
Git commit        → 稳定工件检查点
恢复日志          → 最近检查点之后尚未稳定的执行现场
工作日志          → Project 长程中按 Issue / Work Unit 分区的重要事件
PR                → Issue 中的一次交付与 Review 子范围
```

工作连续性是顶层架构能力。职责划分为：

- **Skills 负责**：判断什么时候记录；判断 observation 对当前工作意味着什么；
  判断是否满足 Claim 和验收；决定下一步以及最终状态。
- **连续性组件负责**：保存和读取记录；绑定 repository、worktree 和 work unit；
  定位检查点；提供恢复所需事实；维护必要的日志不变量。

连续性组件不负责工作流编排，也不判断目标是否达成。

---

## 一、整体模型

当前上下文由以下信息按需构造：

```text
当前 Issue / Spec
+ 当前 Git 状态
+ 当前 PR 状态
+ 当前工作路径上的最近检查点
+ 检查点之后相关的工作日志事件
+ 检查点之前仍未解决的相关事件
+ 当前 worktree 的恢复日志
```

所谓"当前工作状态"不是另一份独立数据库，而是 Agent 在启动或恢复时
根据这些来源重新判断出的结果。上下文是临时构造结果，不是权威状态源。

---

## 二、Git 检查点

### 定义

检查点是一个被显式确认可以承担连续性边界的 coherent Git commit。

Git commit 始终是真实工件历史，但不是每个 commit 都自动成为连续性检查点。
只有工作日志中存在相应事件时，commit 才是检查点：

```yaml
kind: checkpoint-created
work: issue-5
cycle_id: cycle-2
commit: abc123
```

检查点表示：

> 该 commit 对应一个可理解、可继续工作的稳定工件状态。

检查点不表示：Issue 已完成；实现正确；Evidence 充分；验收通过；PR 可以合并。

### 检查点的作用

- 恢复稳定工件；
- 过滤较早的普通工作事件；
- 判断哪些恢复记录已经被本地 commit 吸收；
- 将 Evidence 绑定到明确工件；
- 为接替 Agent 提供恢复起点。

形成检查点前，应确认：

- commit 内容是一致、可理解的工作结果；
- working tree 中相关修改已经被处理；
- 需要保留的长期事件已经进入工作日志；
- 未确认的外部操作没有被错误隐藏。

普通 commit 不自动触发日志过滤和轮转。

### 历史改写

发生 rebase、cherry-pick 或 squash 后，不修改旧事件，而是追加映射：

```yaml
kind: checkpoint-remapped
old_commit: abc123
new_commit: def456
reason: rebase
```

PR squash merge 后记录源 HEAD 和最终 merge commit 的关系。

---

## 三、恢复日志

### 定义和范围

恢复日志是每个活跃 worktree 的临时日志，保护最近检查点之后尚未稳定的执行现场。

恢复日志：

- 绑定具体 repository、worktree 和 work unit；
- 不进入 Git index；
- 不进入 commit；
- 不进入 PR diff；
- 不承担长期项目历史保存。

参考实现把它放在仓库根目录 `docs/journal/recovery/<worktree>/`，
并用 `.gitignore` 整体排除该目录，从机制上保证上述三点，
同时人类仍能在需要时直接翻开这些文件。

一个 worktree 同时只承担一个前台工作意图。并行工作使用独立 worktree 和独立恢复日志。

### 启动时机

当一个 branch 或 worktree 被明确用于推进某个 Issue 或 Work Unit 时：

1. 将 worktree 绑定到该工作；
2. 记录当前 branch、HEAD 和最近检查点；
3. 创建或接续该 worktree 的恢复日志。

普通只读 checkout 不启动工作绑定，例如：checkout `main` 阅读代码、
detached HEAD 查看旧版本、临时切换分支比较实现、没有明确工作目标的检查。

### 普通本地工作

普通本地实现、调试和调查只需记录当前 `intent`：

```yaml
type: intent
work: issue-5
cycle_id: cycle-2
action_id: update-recovery-rules
action: 修改外部操作中断后的恢复规则
scope:
  - work continuity contract
worktree: issue-5-main
base_checkpoint: abc123
head_at_record: abc123
```

它表示：当前已经确定准备做什么。它不证明行动已经发生。

实际本地状态由以下来源表达：working tree、Git diff、staged changes、Git commit。

普通文件编辑不要求记录完整的 `intent → begin → end`，
否则会与 Git 重复，并产生不必要的执行仪式。

### 结果不透明或不能安全重复的操作

只有以下操作才额外记录 `begin / end`：

- 远端写操作；
- 可能部分成功的操作；
- 不能安全重复的操作；
- 中断后无法从 Git 或文件系统判断结果的操作；
- 可能已经生效但响应丢失的操作。

流程为：

```text
intent
→ 持久写入 begin
→ 执行副作用
→ 获得可靠观察
→ 写入 end
```

#### `begin`

必须在副作用发生前可靠持久化。至少记录：目标对象、准备产生的变化、
恢复时如何确认变化是否发生、必要的可识别信息。

```yaml
type: begin
action_id: update-issue-5
target:
  kind: github-issue
  id: 5
expected_change:
  body_contains: "Git 检查点"
recovery_check:
  read_target_before_retry: true
```

#### `end`

在操作返回并获得可靠观察后记录：

```yaml
type: end
action_id: update-issue-5
observation:
  response_received: true
  remote_updated_at: 2026-08-06T14:00:00+08:00
  body_contains: "Git 检查点"
```

`end` 只表示：操作已经返回，观察结果已经记录。
它不表示目标、Claim 或验收已经满足。
`end` 可以如实记录非零退出码或失败响应，而不声明目标失败。

### 恢复判断

```text
只有 intent      → 行动已经确定，但未确认开始
有 begin，没有 end → 操作已经发起，结果未知
存在 end          → 操作已经返回，根据 observation 和当前状态判断下一步
```

出现 `begin` 无 `end` 时：

```text
先读取真实目标状态
→ 判断操作是否已经发生
→ 再决定继续、补偿或重试
```

禁止盲目重复可能已经成功的操作。

### 清理和轮转

恢复日志主要覆盖最近检查点之后的现场。形成新检查点后，
只有同时满足以下条件，才可以轮转或清理旧记录：

- 本地修改已经被 commit 吸收或明确处理；
- 不存在未解释的 `begin` 无 `end`；
- 外部操作结果已经确认；
- 需要长期保留的事件已经提升到工作日志或正式来源；
- 当前 worktree 的下一步已经明确，或工作准备暂停、交接或结束。

不能仅因为创建了 commit 就无条件清理恢复日志。

---

## 四、Project 工作日志

### 生命周期和分区

工作日志机制在整个 Project 生命周期内持续存在，
但不维护一条所有工作共同追加的全局事件流。

工作事件按 Issue / Work Unit 分区：

```text
Project work log
├── issue-5
├── issue-8
└── issue-13
```

每个分区可包含多个处理周期：

```text
issue-5
├── cycle-1
└── cycle-2
```

一个处理周期从该 Issue 开始或重新开始处理，到当前轮工作收敛为止。

Issue 重新打开时：继续使用原 Issue 分区；追加 `work-reopened`；
创建新的 `cycle_id`；保留旧周期作为历史。

一个 Issue 可以跨越：多个 branch、多个 worktree、多个 Agent、多个 PR。
PR merge 或 close 不自动结束 Issue 工作日志。

### 记录内容

工作日志只记录会长期影响理解、判断或恢复的重要事件，例如：

- Issue 开始处理或重新打开；
- 关键调查结论；
- 重要假设被支持或排除；
- 重要方向调整；
- 关键新事实；
- 实质范围变化；
- 检查点形成；
- Evidence 针对某个 commit 产生；
- 后续变化使旧 Evidence 失效；
- Review Finding 被提出或解决；
- remediation 完成；
- worker 结果被主 Agent 吸收；
- HANDOFF；
- PR 创建、关闭或合并；
- commit 映射；
- 当前周期或 Issue 达到最终状态。

普通下一步不进入工作日志。例如"下一步运行定向测试""下一步修改某个文件"
"下一步补充一个场景"，这些只留在恢复日志的 `intent` 中。

只有当下一步变化反映以下情况时，才进入工作日志：重要实现方向改变；
新事实推翻已有假设；工作范围发生实质变化；原方案被排除；
新依赖或风险改变后续路径。

### 不记录内容

工作日志不记录：每次文件读取；每次代码搜索；每次小编辑；每条命令；
完整命令输出；所有工具调用；完整恢复日志；完整聊天；推理轨迹；
没有长期价值的临时探针。

判断标准是：

> 未来恢复或调查这个 Issue 时，这条事件是否会改变对当前方向、风险或历史原因的理解？

### 与 commit 的关联

工作事件应尽量绑定明确的工件位置。按事件类型记录必要的最小字段：

```text
head_at_event
base_commit
subject_commit
result_commit
before_commit
checkpoint
pr
```

例如：

```yaml
seq: 42
kind: verification-observed
work: issue-5
cycle_id: cycle-2
subject_commit: def456
observation:
  check: targeted recovery scenarios
  exit_code: 0
```

该事件表示：在 `def456` 上观察到一次检查结果。
它不直接声明：当前实现正确；当前验收满足；后续 commit 仍被该 Evidence 覆盖。

### 根据检查点过滤

恢复当前工作时，不默认读取整个 Project 或整个 Issue 的全部历史。

先定位当前工作路径上最近的相关检查点，再读取：

```text
该检查点之后的相关工作事件
+ 检查点之前仍被明确标记为未解决或继续相关的事件
```

真正具有长期约束力的决定不能只存在于工作日志中，必须提升到：
Issue、Spec、Policy、Decision Record、PR 中明确保留的决定。
工作日志记录决定发生及其引用，不代替权威决定来源。

### 写入所有权

多个 worktree 可以并行工作，但不并发直接写同一 Issue 分区。

规则为：

- 每个 worktree 独立维护恢复日志；
- worker 返回候选工作事件；
- 主 Agent 或当前 work owner 检查并追加长期事件；
- 不建设分布式锁或全局排序服务。

工作日志可使用分区内单调序号表达追加顺序。时间戳用于阅读，不单独承担因果排序。

---

## 五、PR 的角色

PR 是 Issue 中的一次交付和 Review 子范围：

```text
Issue
├── 调查
├── PR A
├── PR B
└── 最终收敛
```

PR 继续保存：交付 diff；Review；checks；Finding；merge 或 close 状态。

工作日志只保存对 Issue 长程上下文有价值的摘要和引用，不复制完整 PR 时间线。

工作日志事件可以带 `pr` 字段，从而支持：查看整个 Issue；查看某个处理周期；
查看某个 PR；查看某个 commit 之后；查看 verification、review 或 handoff 事件。

恢复日志不属于 PR，也不得进入 PR。

---

## 六、当前状态与历史事件

Git、PR、环境和日志不使用固定的总优先级互相覆盖。它们回答不同问题：

```text
当前读取的 Git、PR 和环境 → 现在是什么
恢复日志和工作日志         → 过去准备做过什么、发起过什么、观察到什么
```

两者看似不一致时：

1. 确认是否指向同一 repository、worktree、branch、commit、PR 或远端对象；
2. 判断记录类型是 `intent`、`begin`、`end` 还是工作事件；
3. 检查记录对应的工件版本；
4. 重新读取当前状态；
5. 重建从历史观察到当前状态之间的变化。

新日志不能被旧 Git 快照否定；当前 Git 状态也不能被历史日志覆盖。
不能仅依赖时间戳决定谁更可信。

---

## 七、上下文恢复

新 Agent、session 或 Runtime 启动时：

```text
1. 读取 Policy 和当前 Issue / Spec
2. 确认 repository、worktree、branch、HEAD 和关联 PR
3. 检查 working tree 与 staged changes
4. 定位当前路径上最近的相关检查点
5. 读取该检查点之后相关的工作日志事件
6. 读取检查点之前仍未解决或继续相关的事件
7. 读取当前 worktree 的恢复日志
8. 查找 begin 无 end 的外部操作
9. 查询对应目标的当前状态
10. 检查 Evidence 是否仍对应当前工件
11. 按当前角色构造必要上下文
12. 确定并记录新的 intent
```

恢复出的上下文至少包含：

```text
当前目标与验收
当前 Git 和 PR 状态
最近检查点
检查点之后的重要变化
仍未解决的旧问题
当前未收敛 intent
结果未知的外部操作
当前有效或失效的 Evidence
下一项可执行行动
```

完整旧聊天不是必要输入。

---

## 八、存储不变量

本契约不冻结通用存储 API 或公共 Schema。参考实现可以使用简单的内部格式，
但任何实现都必须满足以下最低不变量。

### 恢复日志

- 与具体 worktree 绑定；
- 位于 Git metadata 或 Runtime 本地存储（参考实现选择后者，见第四节）；
- 不被 Git 跟踪；
- 不进入 PR；
- 支持追加；
- 能忽略不完整尾部（写入被中断时，损坏的尾部不破坏此前记录）；
- `begin` 必须在副作用前持久化；
- 不保存 secret 或无关敏感信息。

### 工作日志

- 与 repository / Project 关联；
- 不依赖单个 worktree 生命周期；
- 按 Issue / Work Unit 和 `cycle_id` 分区；
- 支持按 commit、PR 和事件类型过滤；
- 跨 session 可读取；
- 不保存完整聊天、推理或工具轨迹。

参考实现把工作日志放在 `docs/journal/work-log/<work>/log.jsonl`，
被 Git 跟踪、随仓库演进；恢复日志放在 `docs/journal/recovery/<worktree>/`，
由 `.gitignore` 排除。两者都在人类可读的仓库文件树下，
但恢复日志通过 ignore 规则保证不进入 index、commit 和 PR diff。

### 实现应支持的操作

```text
绑定 worktree 与 work unit
解除或暂停绑定
记录 intent
记录 begin
记录 end
追加工作事件
显式创建 checkpoint 事件
定位最近相关检查点
读取检查点后的工作事件
读取未解决旧事件
发现 begin 无 end
轮转恢复日志
加载恢复输入
```

### 不属于本契约的范围

- 跨机器同步未提交现场；
- 远程日志服务；
- 多存储后端；
- 分布式一致性。

---

## 九、Skills 与 Runtime 接入

本契约不重新定义现有工作生命周期和角色契约，只增加必要连接。

### Skills

Skills 决定：是否需要记录 intent；哪些操作需要 `begin / end`；
何时形成 coherent checkpoint；哪些事件值得进入工作日志；
observation 对 Claim 的含义；是否需要重新验证；
最终状态是 `DONE`、`BLOCKED` 还是 `HANDOFF`。

### Work Package

按需携带：

```text
work reference
cycle_id
starting commit
starting checkpoint
owned worktree or scope
relevant unresolved events
```

### Result Envelope

worker 返回：实际修改、验证结果、产生的 commit、候选工作事件、
未结束或结果未知的操作。主 Agent 决定哪些候选事件进入长期工作日志。

### `finish-work`

在输出最终状态前确认：

- 没有未解释的 `begin`；
- dirty working tree 已被理解；
- 重要工件已经形成检查点，或未提交现场已明确交接；
- 当前 Evidence 对应当前工件；
- 具有长期价值的事件已经保存；
- 具有约束力的决定没有只停留在日志中。

### Runtime adapter

本契约定义 Runtime 需要接入的能力边界。OMP、Claude Code 等完整接入
在后续 adapter 工作中完成。

---

## 十、这不是什么

本契约不定义、也不应演化为：

- Workflow Engine 或持久工作流状态机；
- DAG、Task Queue、Scheduler、Worker Registry；
- Event Sourcing、Event Bus 或完整日志回放；
- 完整工具调用日志或完整 conversation 归档；
- 独立 Work State 数据库；
- 全 Project 单一追加日志；
- 分布式事务、distributed lock、自动 retry framework；
- 自动判断目标是否达成、自动恢复执行所有操作；
- Dashboard、向量数据库、RAG Memory、通用插件系统。

---

## 与其他文件的关系

- 责任顺序与必要规则：`skills/_shared/work-lifecycle.md`
- 工作单元的目标与验收格式：`skills/_shared/work-unit-contract.md`
- 主 Agent 与 worker 之间的交接格式：`skills/_shared/delegation-contract.md`
- 最终状态语义：`policy/working-contract.md` 的"完成语义"
- 参考实现：`continuity/` 目录（与本契约同属一个 module）
