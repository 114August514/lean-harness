# Git Contract

## 目的与边界

本契约定义 Lean Harness 对 Git 工件的 Runtime-neutral 语义和必要机械不变量，
使不同 Agent Runtime、Git MCP 与本地 Git 实现可以读取同一组事实，并在不代替
工程判断的前提下安全执行明确操作。

职责边界是：

```text
Policy
→ 风险、权限、外部操作、destructive boundary 和最终完成语义

Skills / Agent
→ 何时及为何 branch、stage、commit、merge、rebase、handoff 或 cleanup

Git Contract
→ Git 工件语义、identity、ownership 和机械安全不变量

Continuity
→ intent、Recovery、Shared Work Log、checkpoint、remap 和 resume

Git MCP
→ 读取 Git facts，执行调用方明确指定的 Git 操作

Runtime Adapter
→ 把具体 Runtime 接入上述能力，不改变领域语义
```

Git Contract 不定义团队 branch naming、commit message 格式、默认 merge 策略、
PR 大小、CI、release、LFS、labels 或 milestones。这些是仓库约定或启发式规则，
不是 Harness Core 不变量。

## 领域对象与 identity

### Repository

Repository 是共享同一 Git object database 和 refs 的本地 Git 仓库。linked worktree
共享 repository，但具有各自的 checkout、index、`HEAD` 和 worktree metadata。

本地路径、remote 名称或 remote URL 都不能单独充当跨 clone 的稳定 repository
identity。需要跨 clone 关联时，调用方必须携带已明确的 project / repository
reference；Git 层只报告实际发现的本地根目录、common Git directory 和 remotes。

### Worktree

Worktree 是一个 checkout 及其独立 index、`HEAD` 和工作区状态。主 worktree 与
linked worktree 在 Git 工件语义上地位相同；“主”只描述 repository 布局，不授予
更高工作权限。

checkout path 不是稳定 worktree identity。需要跨 session 关联本地 Recovery 时，
identity 以 [`continuity/contract.md`](../continuity/contract.md) 的 per-worktree
metadata 规则为准。

### Index、working tree 与 path classification

index 是当前 worktree 准备形成下一次 commit tree 的暂存状态；working tree 是文件
系统中的可编辑现场。两者彼此独立，因此“文件内容还在”不表示 index 未改变，
“已经 unstage”也不表示 working tree 修改被撤销。

path classification 至少区分：

```text
tracked
→ index 中存在 entry；即使路径匹配 ignore rule，仍然是 tracked

untracked
→ working tree 中存在、但 index 中没有 entry

ignored
→ untracked path 匹配 ignore rule，默认 status 通常不展示

registered submodule / nested Git repository
→ 自身还包含独立 Git state，不能当作普通目录处理
```

ignored 只影响 Git 的默认发现和添加行为，不表示内容可重建、无价值、不敏感或可安全
删除。`.gitignore` 也不是 secret protection：已 tracked 的文件不会因新增 ignore rule
停止被追踪，显式操作仍可能加入 ignored 内容。

`.gitattributes` 可以改变 normalization、line ending、binary classification、diff /
merge driver 和 clean / smudge filter。working tree bytes、index blob 与最终 checkout
内容因此不一定逐字节相同。Git MCP 必须通过 Git 的 index / attribute 语义执行 stage、
diff 和 checkout 类操作，不用裸文件复制或扩展名猜测替代 Git 结果。LFS 只是 filter 的
一种仓库选择，不进入 Harness Core。

### Ref、branch 与 HEAD

branch 是指向 commit、可随提交或显式操作移动的 ref。`HEAD` 可以：

- symbolic 地指向 branch；
- detached 地直接指向 commit；
- 在尚无首个 commit 时处于 unborn 状态。

事实读取必须保留这三种差异。不得把 detached 或 unborn 伪装成空 branch，
也不得把 branch 名称当作不可变工件 identity。

### Remote 与 remote-tracking ref

remote 是当前 local repository 中的命名配置，不是远端 repository 本身。`origin`、
`upstream` 等名称只是约定，不携带固定 authority。增加、重命名或删除 remote 只改变
本地配置，不创建、移动或删除远端 repository / ref。

remote-tracking ref 是本地保存的远端 ref observation。fetch / prune 更新或删除这些
本地 observations；它们不等于远端写操作。push 才会尝试修改远端 ref，属于需要明确
授权和结果观察的外部 mutation。pull 是 fetch 与本地 integration 的组合，不应被 Git
MCP 当成无需说明 merge / rebase / fast-forward 语义的单一机械步骤。

remote URL 可能包含嵌入式 credential。读取方可以在进程内使用真实配置执行获准操作，
但面向 Agent、人类、日志或共享事件的 facts 必须按 Policy 去除 credential；credential
不是 repository identity 的组成部分，也不得因“它存在于 Git config”而被持久传播。

### Commit

commit 是由 tree、parent、author、committer 和 message 等内容确定的不可变 Git
object。完整 object ID 是该 commit 的 identity；短 hash 只用于无歧义的人类展示。

以下事实彼此不同，必须分别表达：

```text
object 存在
object 的类型是 commit
commit 是另一个 commit 的祖先
commit 可从某个 ref / HEAD 到达
commit 的 tree 或 patch 与另一个 commit 相似
```

内容或 patch 相似不表示 identity 相同；object 尚存在也不表示它仍被 branch、tag、
HEAD 或 Continuity checkpoint 保留。

### PR

PR 是托管平台把 head 变化收敛到 base 的交付和 Review 子范围，不是原生 Git object，
也不是 Issue / Work Unit 的完整状态。PR facts 来自 provider / Continuity adapter，
Git 层只提供其 base/head commit、ref 和 ancestry 所依赖的 Git facts。

## Work Unit、branch、worktree 与 ownership

Work Unit 表达目标、范围、Claims 和验收。branch、worktree、commit 与 PR 是推进或
交付该目标时使用的工件，不与 Work Unit 建立固定一一映射。

一个 active Git context 至少能够回答：

```text
哪个 repository
哪个 worktree
哪个 branch 或 detached HEAD
当前 HEAD
关联哪个 Work Unit / cycle（若已绑定）
谁拥有该可变现场
```

必要不变量：

- 仓库定义的稳定 / 集成分支不作为普通开发现场；对其直接修改或合并遵守 Policy 的共享与发布边界。
- 普通 active modification 使用调用方明确选择的 branch 和当前拥有 writer ownership 的 worktree。
- 一个可变 worktree 同一时刻只有一个 owner；owner 负责其中的 staged、unstaged、untracked、conflict 和 Recovery 现场。
- 一个可能被移动的 branch 同一时刻只有一个 writer。不得用绕过 Git worktree branch protection 的方式让多个 worktree 并发移动同一 branch。
- 并行修改使用不同 worktree，并为会移动的 ref 划分不同 ownership；重叠变化在显式 convergence 操作中整合。
- worktree ownership 是有时间边界的 writer ownership，不是 worker 与 dedicated worktree 的永久绑定。前一位 owner 停止写入并显式交接当前 HEAD / working state、Recovery（存在时）和 movable ref ownership 后，后一位 owner 可以顺序接管同一个 worktree。
- 普通 checkout、fresh clone、CI checkout、临时 detached checkout 或只读检查不会自动成为 active work，也不会隐式取得 ownership。
- detached HEAD 可以用于明确的只读或受控操作；若在其上产生需要保留的 commit，必须先建立保留 ref。checkpoint / handoff 可以记录其语义，但不替代 ref 保存 Git object，也不能依赖 reflog 恢复。
- worktree 或 branch 与 Work Unit 的关联由 Skills / Continuity 记录；不得从名称猜测目标、owner、完成状态或 Recovery binding。

ownership 是协作契约，不是 distributed lock。Git MCP 需要执行可检查的本地保护，
但不建立 worker registry、租约服务或跨机器锁。

## Artifact facts 与读取要求

### 最低 facts

恢复、验证、安全 mutation 和后续 Git MCP 至少需要提供以下事实。

| 范围 | 必须保留的事实 |
| --- | --- |
| repository | 当前路径是否属于 Git repository、worktree root、Git directory、common Git directory、object format（若相关） |
| current worktree | path、本地 identity（若已建立）、主 / linked、lock / prunable observation、branch / detached / unborn、HEAD |
| all worktrees | 每个已注册 worktree 的 path、HEAD、branch / detached、locked / prunable observation |
| ref | 完整 ref name、目标 object ID、symbolic target、upstream（存在时） |
| HEAD | 完整 commit ID，或明确的 unborn / unavailable |
| status | staged、unstaged、untracked 分别列出；每个 path 保留 index / worktree status |
| local path inventory | 调用场景要求时列出 ignored、nested repository、registered submodule 及无法可靠读取的 path |
| conflict | unmerged path 及可用的 stage / mode / object facts，不折叠为普通修改 |
| rename / copy | destination、original path、index / worktree side，以及可用的 similarity observation |
| diff | 明确 comparison endpoints、index / worktree / commit scope、path、status、mode / object IDs，以及调用方请求时的 patch |
| commit | object 是否存在、类型、完整 ID、parents、tree；调用方请求的 ancestry 与 reachability 结果 |
| remotes | remote 名称、fetch / push URL 和相关 ref 配置；缺失与读取失败必须区分 |

事实读取按消费场景扩展，而不是让所有命令返回最大 schema。普通 status 不必总是扫描
ignored 或展开 submodule；但只要后续操作可能覆盖、移动或删除这些内容，它们就成为
该操作的必要 facts，不能继续作为“未请求的可选信息”省略。

命令失败、权限不足、路径不是 repository、目录无法读取或输出无法解析时，结果是
明确 error / unavailable，不是空集合或 clean。reflog、stash、tags、notes 和 provider
facts 继续按真实调用需求读取，不进入所有查询的固定返回负担。

### 结构化读取

实现应使用 Git 为机器提供的稳定格式或 plumbing 能力，并显式固定所依赖的格式版本。
适用的实现依据包括：

```text
status --porcelain=<明确版本> -z
diff --raw / --name-status -z
worktree list --porcelain -z
rev-parse / symbolic-ref / for-each-ref
cat-file
merge-base --is-ancestor
remote get-url
```

这是一组可选实现依据，不是要求 Git MCP 暴露同名命令。实现必须：

- 使用 NUL 边界或等价的无歧义结构保留空格、换行和非 ASCII path；
- 不解析本地化的默认 `status`、`branch`、`log` 或面向人的装饰文本；
- 记录命令退出状态，并区分合法的 false、absent、unborn 与执行 / 解析错误；
- 在跨调用边界和持久事实中使用完整 object ID；
- 不从 branch name、目录名、commit message 或 PR 标题推导领域状态；
- 不因当前 Git 版本支持额外字段，就把该字段变成无真实消费者的 Core schema。

[`continuity/contract.md`](../continuity/contract.md) 当前 reference implementation
可以固定使用满足其字段需求的具体 porcelain 版本；Git Contract 约束的是保真事实，
不要求为文档一致性机械重写已验证的 parser。

## Cleanliness、path inventory 与 loss surface

“Git status clean”和“操作不会丢失现场”是两个不同判断。

任何 cleanliness 结论必须说明覆盖范围。例如只检查 tracked index / worktree、同时检查
普通 untracked，或连 ignored / nested repository 一起检查。默认 `git status` 没有输出
不能证明 ignored 内容不存在；某个 Git 命令不需要 `--force` 也不能证明它不会删除
ignored 或其他未被 status 展示的内容。

可能覆盖、删除或使工件失去可达性的操作，必须先形成与该操作匹配的 loss surface：

```text
将被移动或删除的 refs
可能失去可达性的 commits
将被修改的 index entries
将被覆盖或删除的 tracked working-tree content
untracked paths
ignored paths
registered submodules / nested repositories
per-worktree Git metadata 与 Recovery binding
相关 remote refs 或其他外部状态
```

不要求无差别扫描与操作无关的整个 repository；要求 loss surface 覆盖该操作实际可能
影响的全部对象。每项潜在损失必须属于以下之一：

```text
可从保留工件可靠重建
已验证地转移到另一个 owner / artifact
经有权 authority 明确授权丢弃或覆盖
```

仅记录 handoff、存在 reflog、匹配 ignore rule、可以重新运行命令或“通常是缓存”，
都不能单独证明内容已经被保留或可以丢弃。

## stage 与 commit

stage 和 commit 都是调用方明确发起的 mutation，不是“保存所有当前工作”的快捷方式。

stage 必须：

- 使用明确 path、pathspec 或 hunk selection；
- 保留并报告未被选择的 staged / unstaged / untracked 事实；
- 在完成后重新读取 index，并允许调用方检查实际 staged diff；
- 不以“方便”为由默认吸收未知或不属于当前 owner 的文件。

commit 必须：

- 只消费调用方已确认的 index 内容；
- 使用明确提供或由 Git 配置解析出的 author / committer identity；缺失时返回可诊断错误，不擅自修改 global / repository config；
- 在创建后返回新 commit 的完整 identity、parents、实际 author / committer 和 ref / HEAD 状态；
- 不把 commit message、成功退出或工作区 clean 当作“语义完整”的证明；
- 不默认创建 empty commit、amend 现有 commit 或移动未明确选择的 ref。

诊断 identity 时可以读取 Git 的 effective value 及其 config origin；commit object 中的
实际 author / committer 才是已创建工件的权威事实。Runtime 不应假定 global config、
repository config 或环境覆盖中的任一层永远存在或具有固定优先权。

一次 commit 是否表达 coherent change、何时提交、如何组织提交和采用什么 message，
由 Skills / Agent 与仓库约定决定。Git MCP 只保证 index 与产生的 Git object 可观察。

## Commit 与 Continuity checkpoint

```text
Git commit
→ 真实 Git object、工件快照、parents、identity、ancestry 和 reachability

Continuity checkpoint
→ 被 Skills / owner 判断 coherent，并通过共享事件显式声明的恢复边界
```

普通 commit 不自动成为 checkpoint。Git Contract 只证明候选 commit：

- 存在且类型为 commit；
- 与当前 repository、HEAD 或指定 ref 的 ancestry / reachability 关系；
- 形成 checkpoint 时要求的本地 status facts。

checkpoint 是否 coherent、什么时候发布、哪些长期事件需要提升，以及 rotation 是否
可以推进，由 [`continuity/contract.md`](../continuity/contract.md) 和 Skills 决定。

checkpoint identity 是共享事件 identity，不是可变 branch name。commit 被 history
rewrite 替代后，不得修改旧 checkpoint event；Continuity 通过只追加 remap 把旧
checkpoint identity 解析到新 commit。

## PR convergence

一个 PR 只承载一次可以独立交付和 Review 的 head-to-base convergence sub-scope。
因此允许同一 Issue / Work Unit 使用多个 branch、worktree 和 PR；反过来，不得仅凭
PR 数量或 branch 拓扑推导 Work Unit 拆分。

最低语义是：

- PR identity 与 provider state 不等于 branch identity；branch ref 可以移动。
- Review、Checks 和 Evidence 必须关联被观察的 head commit identity，而不是只关联 branch 名称。
- 新提交、rebase 或 force update 使依赖旧 head 的 Evidence / Review 是否仍有效成为显式判断，不能静默沿用。
- merge commit、rebase merge 或 squash merge 可能产生不同的最终 commit topology 和 identity；合并后必须读取真实 base / resulting commit facts。
- PR merged / closed 只说明该 convergence sub-scope 的 provider 状态，不自动满足 Issue Acceptance，也不自动输出 `DONE`。

PR 模板、Draft 使用、数字化大小限制、reviewer policy、required checks、merge method 和
自动删除 remote branch 都属于 provider / repository policy，不进入本契约。

## History rewrite 与 identity

Git 操作对 identity 的影响如下：

| 操作 | identity / topology 结果 |
| --- | --- |
| fast-forward | 移动 ref，不创建新 commit，不改变已有 commit identity |
| merge（非 fast-forward） | 保留已有 commits，另建具有多个 parents 的 merge commit |
| revert | 保留被撤销 commit，另建表达反向变化的新 commit |
| amend | 以新 commit 替代 branch tip；旧 commit identity 不变但可能失去可达性 |
| rebase | 在新 parent 上重放所选 commits；实际重放的 commits 通常获得新 identity，重复或空变化也可能被跳过 |
| cherry-pick | 从所选变化构造当前 parent 下的新 commit；来源 commit identity 不被继承 |
| squash | 把一个或多个变化收敛为新 commit；被折叠 commits 的 identity 不成为结果 identity |

在极少数所有 commit inputs 完全相同的情况下 object ID 可以碰巧相同；实现仍应通过
读取实际 object ID 判断，不按操作名称假定相等或不等。

Skills / Agent 决定是否以及何时 rewrite。Git Contract 不默认要求 rebase、squash
或线性历史，也不为历史外观无条件牺牲仍有 Recovery、Evidence 或协作价值的 identity。

rewrite 前至少读取：

- 当前 HEAD、branch / detached state 和 upstream / target facts；
- staged、unstaged、untracked 与 conflict；
- 将被移动的 refs 和提交范围；
- 该范围是否包含或承载 Continuity checkpoint；
- 当前 operation / Recovery 是否允许开始。

rewrite 后至少观察：

- 新 HEAD、refs、commit existence 和 ancestry；
- conflict 或 in-progress operation state；
- 本地修改是否仍被保留；
- 每个受影响 checkpoint 的 old / new commit 映射。

受影响 checkpoint 使用 [`continuity/contract.md`](../continuity/contract.md) 定义的
只追加 `checkpoint-remapped`。patch-id、message、时间或 tree similarity 可以辅助人类
确认映射，但不能让 Git MCP 自动决定语义上正确的 remap。

## Mutation 的共同约束

所有 mutation 都遵循同一最小边界：

```text
解析并固定精确 target
→ 读取相关 before facts
→ 建立完整且与操作匹配的 loss surface
→ 检查机械 preconditions
→ 只执行调用方明确指定的一个操作
→ 重新读取 authoritative after facts
→ 返回结果、冲突、未完成状态或可诊断错误
```

机械 precondition 只证明操作可以安全尝试，不证明操作在工程上应该发生。Git MCP：

- 不选择 branch strategy、base、提交范围、commit 内容或冲突答案；
- 不把 `force` 作为跳过 ownership、Recovery、reachability 或 Policy 的通用途径；
- 不隐藏 Git 已进入 merge / rebase / cherry-pick 等中间状态的事实；
- 操作中断或结果不确定时先重读实际 facts，不按失败直接重复；
- 不擅自 stash、discard、commit、abort、continue 或 cleanup 调用方未指定的现场；
- 对 remote / provider mutation 继续遵守 Continuity 的外部副作用观察与 Policy 授权。

跨层 precondition 不把 Git MCP 变成编排器：Git MCP 检查 status、refs、ancestry、
worktree registration 等 Git 可观察事实；调用方负责建立 ownership、Recovery release
和必要授权，并把精确 target 与已作出的决定带到操作边界。缺少任一必要条件时拒绝
操作，而不是由 Git MCP 猜测或补做上游判断。

### 创建 branch / worktree

创建 branch 至少要求调用方明确 repository、完整 start-point 和新 ref name。实现必须
拒绝意外覆盖已有 ref，并返回实际创建的 ref target。

创建 worktree 至少要求调用方明确 repository 和绝对目标路径；相对路径必须在任何
filesystem 或 Git 操作前拒绝。调用方可以明确 branch 或 detached start-point；两者均
未指定时，允许使用 `git worktree add` 的 Git 原生默认语义，并以操作后观察到的实际
registration、HEAD / branch 和 status 为准。实现必须：

- 确认目标路径不会覆盖已有现场；
- 确认 branch 没有被另一个可变 worktree 占用；
- 不使用绕过 other-worktree protection 的选项建立多 writer；
- 创建后读取注册条目、HEAD / branch 和 status；
- 部分失败时报告实际注册和文件系统状态，不用盲目重试掩盖残留。

branch naming、一个 Work Unit 使用几个 branch、何时创建 worktree，由 Skills / Agent
或仓库约定决定。

### merge / rebase 与冲突

merge / rebase 必须由调用方明确 source / upstream、target / onto 和操作模式。开始前
index 和 tracked working tree 必须满足该操作要求，或现有修改已由 owner 通过明确且
可恢复的方式保存；Git MCP 不自动 stash。Git 对 untracked collision 会原生拒绝；
ignored 内容可能被静默覆盖，调用方应通过操作前的 status 读取自行评估风险。

冲突是需要完整报告的 Git 工件状态，不是可以折叠成“命令失败”的字符串。实现必须
保留 unmerged entries、冲突 paths 和 in-progress operation。如何解决冲突由 Skills /
Agent 决定；`abort`、`continue` 或提交解决结果是分别明确的后续操作。

### 错误与操作后观察

实现至少应让调用方区分：

```text
not a repository
missing / unborn ref or HEAD
object missing or wrong type
dirty / conflicted worktree
branch checked out elsewhere
non-fast-forward or ancestry precondition failed
operation already in progress
target exists / target path occupied
permission or command unavailable
structured output unsupported or invalid
operation result unknown / requires observation
```

不要求所有 Runtime 使用相同错误类或 JSON schema；要求这些差异不能被压成空值、
通用 failure 或虚假的成功。

## 安全清理

cleanup 的目标是释放已经不再需要的 Git 工件，不是制造一个看起来 clean 的状态。

### Worktree removal

删除 worktree 前必须确认：

- target 是调用方明确提供的绝对路径，并精确解析到 registered worktree，而不是宽泛路径或当前目录猜测；
- 已完成目标目录的 filesystem inventory，并分类 tracked changes、untracked、ignored、registered submodule、nested repository 和无法读取的内容；
- inventory 中的每项内容都已保留、已验证可重建，或经 Policy 边界明确授权丢弃；
- 需要保留的 commits 已从保留 ref 可达；
- 若存在 Recovery binding，它已按 Continuity 安全 release，且没有未解释的 operation；
- 没有其他执行者仍拥有或使用该 worktree；
- worktree 未被 lock；lock 必须先按其 owner / reason 正常处理，不能通过叠加 `--force` 绕过；
- non-force removal 成功后，registry 与目标路径的实际状态已重新观察。

Git 对 clean worktree 的定义不覆盖所有 loss surface：只含 ignored 文件的 worktree
可以不带 `--force` 被删除。仅有“branch 已 merged”或普通 status clean 因此不足以
证明 worktree 可删。`worktree prune` 只清理经验证已失效的 administrative entry，
不代替工作区保存、handoff 或物理目录清理。

Git-native `worktree remove` 只适用于 linked worktree。删除 main worktree 或整个
repository 是更大的 filesystem / repository lifecycle 操作，不属于 safe worktree
removal 的最低能力。

### Branch deletion

safe local branch deletion 是带显式 retention 判断的领域操作，不等同于固定调用
`git branch -d` 或 `git branch -D`。删除前必须确认：

- 解析到精确 local branch ref、完整 tip object ID，且没有 worktree checkout 它；
- Skills / owner 已把 tip 及其独有 commits 分类为需要保留或允许丢弃；
- 需要保留 identity 时，tip 已是调用方明确指定并解析到完整 tip ID 的 retained ref 的祖先，或相应 commits 可从其他明确 retained refs 到达；
- 无法从 retained refs 到达的 commits 已按 Policy 的“本地破坏式状态操作”获得 owner 授权丢弃；
- 删除时 branch ref 与所有用于证明 reachability 的 retained refs 仍符合开始检查的
  expected object IDs；任一 ref 已移动都必须拒绝并重新判断；
- 删除后 ref 缺失与 commits 的实际 reachability 已重新观察。

实现应使用 compare-and-delete / verify-retained-refs 语义，只在上述 ref observations
仍成立时删除。Git plumbing 可以提供这一机械保护；本契约不固定 CLI 或 MCP 参数。
`git branch -d` 只会相对该
branch 的 configured upstream，或没有 upstream 时相对调用 worktree 的 `HEAD` 判断，
不能替代调用方指定 retained ref 的检查；仅当这些事实恰好与调用方决定一致时，才可
作为额外保护。

squash 后原 branch tip 通常不是 resulting base commit 的祖先。若原 commit identities
仍有 checkpoint、Evidence、Review 或恢复价值，必须建立 retained ref；若只需保留已
收敛内容而不再需要原 identities，则由 owner 按 Policy 明确授权删除。

remote branch deletion 是独立的外部 mutation，需要精确 remote / ref、明确授权和
操作后观察；删除 local remote-tracking ref 或执行 prune 不等于删除 remote branch。

reflog 和 stash 都是有用的本地临时机制，但不是 shared、永久或可替代 checkpoint /
handoff 的恢复保证。不得把“还能从 reflog 找回”作为 destructive cleanup 的前置证明。

## Destructive operations

常见 destructive operation 与必须纳入的 loss surface 包括：

| 操作 | 可能失去的内容或 identity |
| --- | --- |
| `restore` / `checkout` / `switch` 覆盖 | 选定 index / tracked working-tree 内容，以及目标 checkout 会覆盖的 untracked / ignored collision |
| `reset --hard` | 被移动的 ref / HEAD、index、tracked working-tree 内容，以及阻挡目标写入的 untracked paths（包括 ignored） |
| `clean` | pathspec 和选项选中的 untracked；`-x` / `-X` 涉及 ignored；目录与 nested repository 另有扩大范围的选项 |
| `worktree remove` | 目标 worktree 全部 filesystem 内容、独立 index / HEAD 和 worktree metadata；ignored 即使不加 `--force` 也可能被删除 |
| branch ref deletion | branch ref 与删除后可能失去可达性的 commits；`force` 不增加授权，compare-and-delete 只防止并发误删 |
| `push --force` / `--force-with-lease` | remote ref、远端可达性以及依赖旧 identity 的协作者状态 |
| filter / migrate / mass rewrite | 受影响 refs 下的大量 commit identities、checkpoint mappings、PR / Review / Evidence 关联 |

这些操作必须遵守 [`policy/decision-boundaries.md`](../policy/decision-boundaries.md)：

- 未明确授权时，不得用 destructive 操作清除未确认工作或覆盖共享历史；
- 先解析精确 target、读取现状、识别 owner，并完成上述 loss surface；
- 优先使用保留历史和可验证的方式，例如共享历史错误通常使用 revert；
- `--force-with-lease` 降低并发覆盖风险，但仍是共享历史 rewrite，不因此获得默认授权；
- destructive 操作不得用于掩盖 unknown result、跳过 Recovery / handoff 或让检查“变绿”；
- 操作获得授权后仍需执行前置检查与操作后观察，授权不是关闭安全不变量的开关。

如果密钥或凭据进入 Git，第一步是撤销 / 轮换并按安全事件处理；删除文件、增加
commit 或重写历史都不能让已经暴露的凭据重新安全。历史清理范围由有权 owner 决定。

## Git MCP 最小能力边界

本契约只确定后续 Git MCP 的能力范围，不预先设计 tool 名称、参数 schema、provider
framework 或完整 API。

最低 Read 能力覆盖：

```text
repository / current worktree / all worktrees
branch / detached / unborn / HEAD / refs / remotes
staged / unstaged / untracked / conflict / rename / copy
ignored / submodule / nested repository（操作的 loss surface 需要时）
diff
commit existence / type / parents
ancestry / reachability
in-progress operation
effective commit identity / attributes（相关操作需要时）
```

最低 Mutation 能力覆盖：

```text
branch create
worktree create
stage explicit selection
commit confirmed index
merge / rebase 的明确操作与 abort / continue
safe worktree removal
safe local branch deletion
```

push、fetch、remote branch mutation、provider PR 操作和 history filtering 不因“Git 能做”
自动进入最低能力；真实 Runtime 需要时按外部副作用、权限与安全边界单独增加。

Git MCP 不提供：

```text
next_step
finish_issue / decide_done
auto_merge_when_ready
workflow state machine
automatic branch / commit / rebase strategy
automatic conflict resolution
automatic checkpoint coherence or remap judgment
```

MCP 可以报告 mechanical preconditions 和 facts，但不能把启发式建议伪装成 Git 事实。

## Walkthrough invariants

以下场景用于审查实现或 Adapter 是否保持本契约，不要求建设永久 workflow tests：

1. 创建独立 worktree：从明确 commit 创建新 branch / worktree，注册信息、HEAD、ownership 和 Recovery 各自明确。
2. 并行修改：两个 owner 使用不同 worktree 和 branch；没有共享 index、同 branch 多 writer 或未声明的重叠 ownership。
3. 顺序交接：前一位 owner 停止写入并交接当前工件、Recovery 和 ref ownership 后，后一位 owner 接管同一个 worktree；不要求为每个 worker 新建 dedicated worktree。
4. 只读检查：read-only worker 可以读取共享 checkout，但不因此获得 worktree 或 ref writer ownership。
5. 同步稳定分支：先读取目标与 ancestry，再显式选择 merge / rebase；Contract 不替调用方选择策略。
6. rebase 后 remap：被重放 commit 获得实际新 ID；旧 checkpoint event 保留并只追加无分叉 remap。
7. squash merge：PR head commits 与 resulting base commit identity 分离；PR merge 不自动令 Work Unit `DONE`。
8. dirty / ignored handoff 与 cleanup：普通 status clean 但仍有唯一 ignored 文件时 removal 拒绝；未提交现场、Recovery 和需要保留的 commits 均有可靠去向后才允许删除。
9. safe branch deletion：branch 未被 checkout；需要保留的 identities 已由明确 retained ref 承接，其余已获 owner 授权；ref 仅在仍等于 expected tip 时删除。
10. destructive cleanup：未知或唯一现场不能通过 `force` 消失；操作进入 Policy 授权边界。

## 明确不包含

- Git Workflow Engine 或持久工作流状态机；
- 自动 branch planner、commit planner、merge policy 或完成判断；
- repository state database、后台 Git daemon 或 distributed lock；
- provider / plugin framework 或 Runtime registry；
- 自动 merge、release 或部署系统；
- 完整 Git MCP API 设计或 reference implementation；
- 仓库专属 naming、LFS、CI、labels、milestones、release 和数据目录规则；
- 以数字强制 Issue、commit 或 PR 大小；
- repository-wide directory taxonomy 重构。
