# Work Continuity Contract

## 目的与边界

工作连续性让 replacement agent 或另一位协作者在没有旧模型上下文时，从持久事实
恢复工作。它是顶层能力，不是单一 Skill，也不是工作流引擎。

连续性组件只负责：

- 保存、读取和组合事实；
- 保护结果不透明且不可安全重复的副作用；
- 把显式发布的 checkpoint 与普通 commit 区分；
- 提供 replacement context。

连续性组件不负责判断：

- Claim 是否成立；
- Acceptance 是否满足；
- 工作是否 DONE；
- 哪个产品方向正确；
- 是否应自动重试任意外部操作。

这些判断仍由相应 Skill 和人类完成。

参考实现由五个能力群组成：Local Recovery、Project-shared Work Log、Artifact
Facts、Context Reconstruction 和 Observable Interface。Artifact Facts 覆盖 Issue /
Spec、repository/worktree、Git 工件、PR、Review 与 Checks 的当前事实。

identity、canonical encoding、domain errors、atomic local storage 和 external command
execution 是支撑这些能力的通用机制，不构成额外领域层或基础设施系统。

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
+ 较早但仍未解决的共享事件
+ 当前 worktree、当前 binding 的本地恢复日志
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

每次 `bind` 产生新的稳定 `binding_id`，并创建独立的只追加日志文件。所有记录
必须包含当前：

```text
binding_id
work
cycle_id
```

包括 `bound`、`intent`、`begin`、`end`、operation handoff、pause、release 和
rotation。读取 `latest_intent` 或 `open_begins` 时只扫描当前 binding 的日志。

因此：

```text
issue-5 generation
→ safe release
→ issue-9 generation
→ 不读取 issue-5 的 intent / begin / end
```

旧 generation 可以保留用于诊断，但不得进入当前恢复输入。

唯一例外是仍未获得可靠 observation 的 operation handoff：它属于 worktree 级
`pending_handoffs` 安全视图，必须跨 binding 保持可发现，直到按稳定
`handoff_id` 把 observation / `end` 记录回原 binding。它不得作为新 work/cycle 的
intent 混入 Context Reconstruction，但必须继续由 `recovery status` 暴露。

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

handoff 允许 release / rebind 后，组件仍必须跨 binding 暴露该未解决
operation，并提供把可靠 observation 关联回原 begin 的领域操作。归档旧日志
不能使 handoff 从正常恢复入口消失。

调用方不能用 `force` 绕过该不变量。

### 持久化安全

关键 binding state 使用：

```text
temporary file → flush → fsync → atomic replace → directory fsync
```

更新中断后，读取方要么看到旧完整状态，要么看到新完整状态。损坏、不完整或类型
错误的状态必须变成可诊断 domain error，不得暴露裸 `JSONDecodeError`。

只追加日志文件的最后一条半写记录可以截断；中间损坏必须报错。
读取尾部、判断修复位置和执行截断必须处于同一互斥区间，修复不得
依据加锁前的旧快照删除并发 writer 已经完成的记录。

首次创建日志文件时必须同步其目录项。bind、begin/end、release、rebind 和 rotation
这类"读取不变量再更新"的复合操作必须使用同一 worktree 本地文件锁；不支持所需
锁语义的本地文件系统必须报错，不能静默降级。该锁只保护一个 clone/worktree 的
Recovery，不是 distributed lock。

## Project-shared Work Log

### GitHub Issue comment 是参考实现

当前 GitHub 项目使用 Issue 中的结构化 work-event comments。一个长期事件对应一条
comment，comment 同时具有：

- 稳定 HTML 机器标记；
- 人类可直接阅读的 kind 与 summary；
- 带围栏的 JSON payload。

marker 形如：

```html
<!-- lean-harness-work-event:v1 event_id=evt-... -->
```

payload 是 marker 行之后紧跟的 ` ```json ` 围栏内容。

事件至少包含：

```text
event_id
kind
work
cycle_id
producer
created_at
summary or observation
artifact identity（相关时）
references / resolves when relevant
```

`checkpoint-created`、`checkpoint-remapped`、`event-resolved`、
`verification-observed` 和 `work-reopened` 是具有专用领域不变量的结构性 kind，必须
通过对应操作形成。普通重要事件的 kind 不由 continuity 建立封闭枚举；
Skills / owner 判断其意义和是否值得发布，continuity 只要求它具有合法的基础结构。

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
- 测试用的确定性 fake shared store。

port 的输入是领域层已经验证的 canonical event；实现必须在远端数据进入进程时验证
marker、payload、partition 和 provider response，并只向领域层返回已验证事件。同一
对象在进程内调用链中不重复验证；从 remote 或 Recovery Log 重新载入时必须重新验证。
`list_events` 和 `find_event` 返回已经按 event identity 逻辑去重、并完成冲突检测的
事件；上层 reader 信任该 port，不重复执行同一投影。

不得把该 port 演化为 provider registry、transport framework、后台 daemon、独立
数据库、Event Store 或 Event Bus。

OMP 接入中的官方 GitHub MCP 是唯一 Agent-facing GitHub Provider。GitHub Issue
shared store 是 Continuity Core 内部的固定 domain port，不向 Agent 暴露 GitHub
命令或任意 request。当前 `GitHubWorkState` 只能：

```text
append/list/find canonical work-event comments
read recovery 所需的最小 Issue / PR / check facts
```

它不得创建普通评论、修改 Issue / PR、提交 Review、触发 Checks 或执行 hosted merge，
也不得增加 endpoint passthrough。Agent 发起的这些操作必须通过当前 Runtime 选择的
GitHub Provider。该区分保持 Continuity durable authority 独立于 Runtime session，
同时避免形成第二个等价 GitHub mutation surface；若 port 的能力需要扩大，必须重新
评估 Provider authority collision。

### 身份、顺序与解决关系

`event_id` 是稳定事件身份。多个协作者可以对同一 Issue 并发追加不同 event_id。
不得用本地计算的整数序号表达全 Project 顺序，也不建立全局序列分配器。

相同 `event_id` 与相同 canonical payload 表示幂等重复；相同 `event_id` 与不同
payload 表示身份冲突，必须产生可诊断错误。append confirmation 和 response-loss
reconciliation 都必须比较预期事件与远端事件，不能只确认 identity 存在。

canonical payload 是事件的全部持久字段，但不包括 provider `remote` observation。
事件必须只包含 JSON-native 值；身份一致性通过完整 canonical payload 比较，而不是
额外的派生 digest。并发 writer 可能产生多个物理 comment，因此不承诺 distributed
exactly-once。相同 identity/payload 的物理 comment 在读取时折叠为第一次出现位置上
的一个逻辑事件；不同 payload 的同 ID 使整个 lookup 失败，不得任选其一，也不得为
未知 publication 补写成功 `end`。

展示和 checkpoint 后增量读取使用共享 comment 返回顺序；因果关系使用稳定引用。
解决关系必须写成：

```json
{"resolves": ["evt-previous"]}
```

不得使用分区内整数。

### 写入所有权与正式决定

共享 Work Log 保存稀疏、长期有价值的事实：发生了什么、基于哪个工件、正式决定
在哪里、哪些问题仍未解决。它不是唯一事实库，也不是 Event Sourcing。

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

不需要通用 retry framework。publication coordinator 在写前查询并在写后确认；
GitHub comment API 不提供 event identity 的原子唯一性。GitHub adapter 与 fake store
都必须在读取时执行逻辑去重和冲突检测，fake 还必须能模拟“远端已 append、调用方
收到 response loss”。

## Checkpoint、rotation 与历史改写

### 显式 checkpoint

普通 Git commit 是真实工件历史，但不自动成为 continuity checkpoint。只有共享
日志中真实存在的 `checkpoint-created` 事件才能声明 checkpoint。

公共能力必须区分：

- 追加普通重要事件；
- 创建 checkpoint；
- remap checkpoint；
- 重新打开 work；
- 解决 event；
- 记录验证观察。

generic append 不得构造结构性事件。

### rotation

rotation 接受 `checkpoint_event_id`，并验证：

- 事件从 shared store 真实读取且 kind 为 `checkpoint-created`；
- event 的 work / cycle 与当前 binding 一致；
- remap 后 commit 在本地存在；
- commit 是当前 HEAD 的祖先，位于当前工件路径；
- staged / unstaged / conflict / rename 等本地修改已被吸收或有明确处理；
- 没有未解释的远端操作；
- 调用方已明确确认：其判断需要长期保留的事件已经提升；
- 调用方给出的下一项 intent 非空。

rotation 推进边界的同时原子地写入一条 `intent` record，使 `latest_intent` 立即
反映新阶段行动；binding state 中的 `next_intent` 字段只是该 record 的镜像，不是
独立的意图来源。

最后两项是 continuity 保存的调用方 observation，不是组件对工程意义的独立证明。
哪些事件值得提升、commit 是否完整、下一项 intent 是否合适仍由 Skills / owner
判断。CLI 使用 `--ack-durable-events-promoted` 和 `--next-intent` 明确这一区别。

"commit 是 HEAD 的祖先"只是必要条件，不是全部条件。rotation 不得提供
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

解析从 checkpoint identity 开始沿只追加的 remap chain 前进。fresh clone 必须
仅凭 Git 和共享日志解析到新 commit。

同一 checkpoint 与 `old_commit` 可以有多条指向相同 `new_commit` 的物理/逻辑记录；
若它们指向不同新 commit，则映射已经分叉，必须报告 conflict，不得依赖 comment
顺序任选一条。

## Context Reconstruction

Context Reconstruction 只收集和组合：

- Issue / Spec facts；
- 当前 PR facts；
- `git status --porcelain=v1 -z` 的结构化现场；
- 当前 cycle 中、从 HEAD 可达的最近共享 checkpoint（按 Git 祖先关系取最靠后者）；
- checkpoint 后的共享事件；
- checkpoint 之前仍未解决的共享事件；
- 当前 worktree 当前 binding 的本地 intent / open begins。

Git change 至少包含：

```text
index_status
worktree_status
path
original_path when renamed/copied
conflict
```

默认 Git status 不展示 ignored paths，Recovery Log 也不保存 working-tree 内容。
需要继续使用的 ignored 或其他 local-only artifact 必须由 owner 在 intent / handoff 中
显式引用，并说明其实际保存位置与恢复方式；仅记录路径不能让内容跨 worktree 或 clone
恢复。敏感内容仍按 Policy 处理，不得为了连续性写入 Git 或共享日志。

显式 `resume --work X --cycle Y` 与活跃/暂停的本地 binding 不一致时必须拒绝。
CLI 调用方可显式请求 `shared_only`；Python API 通过不提供 `RecoveryLog` 表达同一
模式。此时只加载共享与 Git 上下文，不创建 Recovery、不读取本地 state、不创建
worktree identity，也不从本地 binding 推导 work / cycle。shared-only resume 至少
需要显式 work。

Issue / Spec 和 PR facts 都必须区分 `present`、`absent`、`unavailable` 和解析
`error`。最低 PR 读取范围只包括恢复所需的 identity/state、base/head、head SHA、
merge state、review decision 和当前 checks 摘要；不复制完整 review comments、
check logs 或 PR 时间线。

fresh clone 没有上一位协作者的 Recovery Log 是正常现象。Issue / Spec + Git / PR +
Shared Work Log 必须足以恢复 checkpoint、方向变化、Evidence、Review Finding、
HANDOFF 和未解决工作；新协作者随后建立自己的 binding。

## CLI 与可观察性

Work Log 不是 AI 私有日志。人类可在 Issue 直接阅读，也可用 CLI：

```text
shared list
shared find
shared unresolved
shared latest-checkpoint
resume
recovery status
recovery resolve-handoff
```

参考实现以 uv 管理 Python 环境，但不是需要构建或安装的发布 package：

```bash
cd continuity
uv run python -m continuity --help
```

写入操作使用 dedicated subcommand；本地 `recovery status` 不依赖 GitHub remote。
CLI/API 的错误也是可观察输出，必须保留 corruption、identity conflict、binding /
checkpoint mismatch 与工件不可用的差异，不能统一降级成空值。

## Skills、完成检查与 Git 最小不变量

Skills 判断哪些事实重要、checkpoint 是否完整、Evidence 是否支持 Claim，以及
最终状态；continuity 保存、读取和组合事实。

完成阶段至少确认：

- 没有未解释的 `begin`；
- dirty working tree 已 commit、明确处理或形成可恢复 handoff；
- 具有工作价值的 ignored / local-only artifact 已实际保留并显式交接，或已确认可重建；
- 完整 checkpoint 已作为共享事件发布，或未稳定现场仍被本地 recovery 保护；
- Evidence 对应当前工件；
- 长期事件已经发布；
- 正式决定没有只停留在 Work Log。

本契约依赖的 Git 最小不变量只有：

- 每位并发执行者使用隔离 worktree；
- checkpoint 必须显式发布且完整；
- commit 可达性是工件相关性的必要事实；
- staged / unstaged / conflict / rename 状态必须保留；
- ignored / local-only artifact 不会自动进入 Git status 或 Recovery，具有工作价值时必须显式处理；
- rebase / squash 使用只追加 remap；
- Recovery Log 不进入 Git；
- Shared Work Log 不属于任何 branch。

Git usage、worktree、ref 和 cleanup mechanics 以
[`substrates/git/contract.md`](../substrates/git/contract.md) 为准；checkpoint、remap、Recovery、handoff 和
resume 语义由本契约定义。本节只保留 Continuity 直接依赖的最小连接点，不重复展开
Git mechanics。

## 验收场景

参考实现使用最小、非重复的自动化场景集合覆盖：

1. 本地 intent、未提交修改和结构化 Git status 可由 replacement 恢复；
2. shared event 发布在响应丢失后按 event_id 恢复，且身份冲突不会被误认为幂等；
3. 两个独立 clone 可从共享 checkpoint、后续事件和未解决事件交接并继续；
4. binding 隔离，open begin 阻止 release/rebind，可恢复 handoff 跨 binding 保持可见；
5. squash / rebase remap 保持只追加，并可由 fresh clone 解析；
6. binding state 和 recovery journal 在中断、损坏与并发修复下保持可诊断；
7. rotation 验证显式 shared checkpoint、本地修改和未知远端操作；
8. GitHub adapter 的 comment protocol 与最小 Issue/PR facts/availability 可确定性验证；
9. CLI 入口和 shared-only / local-only 边界可执行。

同一规则优先只在最接近其责任的稳定层级测试；只有跨模块连接本身构成实质风险时
才增加 E2E，不在 fake、adapter 和 E2E 层机械重复完整场景。

验证证据至少包括全量 tests、lint、compile/static check 和 CLI smoke test。

## 明确不包含

- Workflow Engine 或持久工作流状态机；
- Event Sourcing、Event Store、Event Bus 或完整 replay；
- Task Queue、Scheduler、Worker Registry；
- 后台同步 daemon 或独立数据库；
- distributed lock；
- 任意 provider plugin system；
- 多 Runtime 完整 adapter；
- 跨机器同步未提交 working tree；
- 自动判断 Claim、Acceptance 或最终状态；
- 自动重试所有外部操作；
- Dashboard。
