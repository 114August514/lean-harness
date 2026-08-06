# Work Continuity Contract

## 目的与边界

工作连续性让 replacement agent 或另一位协作者在没有旧模型上下文时，从持久事实
恢复工作。它是顶层能力，不是单一 Skill，也不是工作流引擎。

连续性组件只负责：

- 保存、读取和组合事实；
- 保护结果不透明且不可安全重复的副作用；
- 把显式 coherent checkpoint 与普通 commit 区分；
- 提供 replacement context。

连续性组件不负责判断：

- Claim 是否成立；
- Acceptance 是否满足；
- 工作是否 DONE；
- 哪个产品方向正确；
- 是否应自动重试任意外部操作。

这些判断仍由相应 Skill 和人类完成。

## 三层事实模型

```text
共享层
├── Issue / Spec
├── Git commits
├── PR / Review / Checks
└── Project-shared Work Log

本地层
├── working tree
├── staged changes
└── per-worktree Recovery Log

临时层
└── Agent / model context
```

恢复输入为：

```text
Issue / Spec
+ 当前 Git / PR
+ 最近可达的共享 checkpoint
+ checkpoint 后的共享工作事件
+ 较早但仍 unresolved 的共享事件
+ 当前 worktree、当前 binding generation 的本地恢复日志
→ replacement context
```

共享层跨协作者、机器和独立 clone 可读；本地层不跨 clone；临时层随 session
消失。任何设计不得把三者混成同一种持久状态。

## Local Recovery Log

### 位置与身份

Recovery Log 必须位于：

```text
<git-common-dir>/lean-harness/recovery/<stable-worktree-id>/
```

`stable-worktree-id` 由当前 worktree 的 Git metadata 生成并持久关联。checkout 路径
或 basename 不是身份。linked worktree 与主 worktree 必须得到不同 identity；同一
worktree 重新打开时 identity 保持不变。

Recovery Log：

- clone-local；
- per-worktree；
- 不进入 checkout、index、commit 或 PR；
- 不向其他协作者承诺可见性。

### Binding generation

每次 `bind` 产生新的稳定 `binding_id`，并创建独立 append-only journal。所有记录
必须包含当前：

```text
binding_id
work
cycle_id
```

包括 `bound`、`intent`、`begin`、`end`、operation handoff、pause、release 和
rotation。读取 `latest_intent` 或 `open_begins` 时只扫描当前 binding journal。

因此：

```text
issue-5 generation
→ safe release
→ issue-9 generation
→ 不读取 issue-5 的 intent / begin / end
```

旧 generation 可以保留用于诊断，但不得进入当前恢复输入。

### intent / begin / end

普通本地工作只记录 `intent`。只有结果不透明或不可安全重复的副作用才使用：

```text
intent → durable begin → side effect → reliable observation → end
```

`end` 只表示可靠 observation 已记录，不表示目标、Claim 或 Acceptance 成立。

`begin` 无 `end` 表示结果未知。replacement 必须先查询真实目标状态，不得按失败
处理，也不得直接重复执行。

### release / rebind / rotation 不变量

存在未解释的 `begin` 无 `end` 时，组件必须拒绝：

- release；
- rebind；
- rotation。

解除阻断只能通过：

- 查询真实目标并记录 observation + `end`；或
- 记录明确、可恢复的 operation handoff，包含下一位协作者可执行的查询/恢复步骤。

调用方不能用 `force` 绕过该不变量。

### 持久化安全

关键 binding state 使用：

```text
temporary file → flush → fsync → atomic replace → directory fsync
```

更新中断后，读取方要么看到旧完整状态，要么看到新完整状态。损坏、不完整或类型
错误的状态必须变成可诊断 domain error，不得暴露裸 `JSONDecodeError`。

append-only recovery journal 的最后一条半写记录可以截断；中间损坏必须报错。

## Project-shared Work Log

### GitHub Issue comment 是参考实现

当前 GitHub 项目使用 Issue 中的结构化 work-event comments。一个长期事件对应一条
comment，comment 同时具有：

- 稳定 HTML machine marker；
- 人类可直接阅读的 kind 与 summary；
- fenced JSON payload。

marker 形如：

```html
<!-- lean-harness-work-event:v1 event_id=evt-... -->
```

事件至少包含：

```text
event_id
kind
work
cycle_id
producer
created_at
summary or observation
artifact identity when relevant
references / resolves when relevant
```

示例：

```json
{
  "event_id": "evt-...",
  "kind": "checkpoint-created",
  "work": "issue-5",
  "cycle_id": "cycle-1",
  "producer": "agent:example",
  "created_at": "2026-08-06T10:00:00Z",
  "commit": "abc123...",
  "summary": "Complete the shared work-log reference implementation"
}
```

### 窄 shared-store port

共享存储边界只有当前真实需求：

```text
append_event(work, event)
list_events(work)
find_event(work, event_id)
```

实现为：

- GitHub Issue shared store；
- deterministic fake shared store for tests。

不得把该 port 演化为 provider registry、transport framework、后台 daemon、独立
数据库、Event Store 或 Event Bus。

### 身份、顺序与解决关系

`event_id` 是稳定事件身份。多个协作者可以对同一 Issue 并发追加不同 event_id。
不得用本地计算的整数 `seq` 表达全 Project 顺序，也不建立全局序列分配器。

展示和 checkpoint 后增量读取使用共享 comment 返回顺序；因果关系使用稳定引用。
解决关系必须写成：

```json
{"resolves": ["evt-previous"]}
```

不得使用分区内整数。

### 写入所有权与正式决定

共享 Work Log 保存稀疏、长期有价值的事实：发生了什么、基于哪个工件、正式决定
在哪里、哪些问题仍 unresolved。它不是唯一事实库，也不是 Event Sourcing。

具有约束力的内容必须提升到 Issue、Spec、Policy、Decision Record 或 PR 中明确
保留的决定。协作者或 worker 产生候选事件时，负责吸收结果的 owner 决定哪些事件
值得发布；每条已发布事件必须保留真实 producer identity。

## Shared event 发布与未知远端结果

共享写入本身是远端副作用，必须接入 Recovery Log：

```text
生成稳定 event_id
→ 写 local intent
→ 持久写 begin（保存完整预期事件和 find-by-event-id 恢复方式）
→ append GitHub Issue comment
→ find_event(work, event_id) 确认远端存在
→ 写 end
```

若 comment 已创建但响应丢失：

```text
replacement 发现 begin 无 end
→ find_event(event_id)
→ 已存在：补 end，不重复发布
→ 不存在：保持 absent，只有显式授权后才重试
```

不需要通用 retry framework。GitHub store 自身按 event_id 查重；fake store 必须能
模拟“远端已 append、调用方收到 response loss”。

## Checkpoint、rotation 与历史改写

### 显式 checkpoint

普通 Git commit 是真实工件历史，但不自动成为 continuity checkpoint。只有共享
日志中真实存在的 `checkpoint-created` 事件才能声明 checkpoint。

公共能力必须区分：

- append ordinary significant event；
- create checkpoint；
- remap checkpoint；
- reopen work；
- resolve event；
- record verification observation。

generic append 不得构造结构性事件。

### rotation

rotation 接受 `checkpoint_event_id`，并验证：

- 事件从 shared store 真实读取且 kind 为 `checkpoint-created`；
- event 的 work / cycle 与当前 binding 一致；
- remap 后 commit 在本地存在；
- commit 是当前 HEAD 的 ancestor，位于当前 artifact path；
- staged / unstaged / conflict / rename 等本地修改已被吸收或有明确处理；
- 没有未解释的远端操作；
- 需要长期保留的共享事件已经确认发布；
- 下一阶段明确。

“commit 是 HEAD 的 ancestor”只是必要条件，不是全部条件。rotation 不得提供
`--force` 绕过上述语义。

### remap

rebase、cherry-pick 或 squash 后不得修改旧 checkpoint event。发布新的：

```text
checkpoint-remapped
checkpoint_event_id
old_commit
new_commit
reason
```

解析从 checkpoint identity 开始沿 append-only remap chain 前进。fresh clone 必须
仅凭 Git 和共享日志解析到新 commit。

## Context Reconstruction

Context Reconstruction 只收集和组合：

- Issue / Spec facts；
- 当前 PR facts；
- `git status --porcelain=v1 -z` 的结构化现场；
- 最近可达、当前 cycle 的共享 checkpoint；
- checkpoint 后的共享事件；
- checkpoint 之前仍 unresolved 的共享事件；
- 当前 worktree 当前 binding generation 的 local intent / open begins。

Git change 至少包含：

```text
index_status
worktree_status
path
original_path when renamed/copied
conflict
```

显式 `resume --work X --cycle Y` 与活跃/暂停的本地 binding 不一致时必须拒绝。
调用方可显式请求 `shared_only`，此时只加载共享与 Git 上下文，不混入本地日志。

fresh clone 没有上一位协作者的 Recovery Log 是正常现象。Issue / Spec + Git / PR +
Shared Work Log 必须足以恢复 checkpoint、方向变化、Evidence、Review Finding、
HANDOFF 和 unresolved 工作；新协作者随后建立自己的 binding。

## CLI 与可观察性

Work Log 不是 AI 私有日志。人类可在 Issue 直接阅读，也可用 CLI：

```text
shared list
shared find
shared unresolved
shared latest-checkpoint
resume
recovery status
```

参考实现以 uv 管理 Python 环境，但不是需要构建或安装的发布 package：

```bash
cd continuity
uv run python -m continuity --help
```

写入操作使用 dedicated subcommand；本地 `recovery status` 不依赖 GitHub remote。

## Skills、完成检查与 Git 最小不变量

Skills 判断哪些事实重要、checkpoint 是否 coherent、Evidence 是否支持 Claim，以及
最终状态；continuity 保存、读取和组合事实。

完成阶段至少确认：

- 没有未解释的 `begin`；
- dirty working tree 已 commit、明确处理或形成可恢复 handoff；
- coherent checkpoint 已作为共享事件发布，或未稳定现场仍被本地 recovery 保护；
- Evidence 对应当前 artifact；
- 长期事件已经发布；
- 正式决定没有只停留在 Work Log。

本契约依赖的 Git 最小不变量只有：

- 每位并发执行者使用隔离 worktree；
- checkpoint 必须 explicit 且 coherent；
- commit reachability 是 artifact 相关性的必要事实；
- staged / unstaged / conflict / rename 状态必须保留；
- rebase / squash 使用 append-only remap；
- Recovery Log 不进入 Git；
- Shared Work Log 不属于任何 branch。

完整 Git 工作契约属于独立 Issue，不在本能力中展开。

## 验收场景

参考实现必须以自动化测试覆盖：

1. 本地 intent + 未提交修改可由 replacement 恢复；
2. coherent commit 发布共享 checkpoint 后可安全 rotation；
3. 远端 append 成功但响应丢失时按 event_id 补 end，不重复 append；
4. 两个独立 clone 仅共享 Issue / Git / PR / Work Log 即可交接并形成下一 checkpoint；
5. 新 binding 不读取旧 generation，open begin 阻止 release / rebind；
6. squash / rebase remap 可由 fresh clone 解析；
7. state 更新中断保留旧完整状态，损坏状态产生 domain error；
8. 两位协作者的不同 event_id 都保留，resolves 使用 event_id；
9. structured Git status 保留 index / worktree / rename / conflict；
10. rotation 拒绝非共享显式 checkpoint。

验证证据至少包括全量 tests、lint、compile/static check 和 CLI smoke test。

## 明确不包含

- Workflow Engine 或持久工作流状态机；
- Event Sourcing、Event Store、Event Bus 或完整 replay；
- Task Queue、Scheduler、Worker Registry；
- 后台同步 daemon 或独立数据库；
- distributed lock；
- arbitrary provider plugin system；
- 多 Runtime 完整 adapter；
- 跨机器同步未提交 working tree；
- 自动判断 Claim、Acceptance 或最终状态；
- 自动重试所有外部操作；
- Dashboard。
