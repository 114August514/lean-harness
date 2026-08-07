# Work Continuity Index

本文件是工作连续性能力的常驻入口。

完整语义以 [contract.md](contract.md) 为准。本文件只保留核心模型、不可违反的
不变量和按需阅读导航，不替代权威契约，也不复制事件 schema、恢复算法或实现说明。

## 核心模型

```text
模型上下文
→ 可丢弃的临时信息
Issue / Spec
→ 目标、范围、验收和正式决定
Git
→ 当前工件与提交历史
Project-shared Work Log
→ 跨协作者的重要工作事件
Local Recovery Log
→ 当前 clone/worktree 在 checkpoint 后的未提交现场
PR
→ Issue 中的一次交付与 Review 子范围
```

## 核心不变量

- Work Log 是 Project-shared，并按 Issue / Work Unit 分区。
- Recovery Log 是 clone 本地、按 worktree、按 binding 隔离的。
- Recovery Log 不进入 Git，也不承担跨协作者同步。
- 普通本地工作只记录 `intent`。
- 结果不透明、不可安全重复或可能部分成功的操作使用 `begin / end`。
- `begin` 无 `end` 表示结果未知；重试前必须查询真实目标状态。
- 相同 event identity 的物理重复只算一个逻辑事件；不同内容必须报冲突。
- Git commit 不自动成为 checkpoint。
- 只有显式发布的 checkpoint event 才形成连续性边界。
- 正式决定不能只存在于 Work Log，必须提升到 Issue / Spec / Policy / PR。
- Continuity 只保存、读取和组合事实；Skills 负责解释、验证和完成判断。
- 不从日志重放工作，也不建立 Workflow Engine 或 Event Sourcing。

## 按需阅读

普通本地实现保持上述核心不变量即可。只有准备执行下列特定动作时，才按场景
读取完整契约。

### 启动或恢复工作

阅读 [contract.md](contract.md) 的：

- “三层事实模型”；
- “Context Reconstruction”；
- “Local Recovery Log”。

### 绑定、暂停、释放或推进 worktree

阅读 [contract.md](contract.md) 的：

- "Local Recovery Log"及其"Binding generation"；
- "release / rebind / rotation 不变量"；
- "Checkpoint、rotation 与历史改写"。

### 执行外部写操作

阅读 [contract.md](contract.md) 的：

- “intent / begin / end”；
- “Shared event 发布与未知远端结果”。

### 发布工作事件或形成 checkpoint

阅读 [contract.md](contract.md) 的：

- “Project-shared Work Log”；
- “Shared event 发布与未知远端结果”；
- “Checkpoint、rotation 与历史改写”。

### 委派和交接

阅读：

- [contract.md](contract.md) 的“写入所有权与正式决定”和 release / handoff 不变量；
- [`skills/_shared/delegation-contract.md`](../skills/_shared/delegation-contract.md)；
- [`skills/_shared/work-lifecycle.md`](../skills/_shared/work-lifecycle.md)。

### 完成工作

阅读：

- [contract.md](contract.md) 的“Skills、完成检查与 Git 最小不变量”；
- [`skills/finish-work/SKILL.md`](../skills/finish-work/SKILL.md)。

## Authority

发生冲突时，按以下顺序定位权威来源：

1. 当前 Issue / Spec 的明确目标和验收；
2. [`policy/decision-boundaries.md`](../policy/decision-boundaries.md) 的安全、外部契约和禁止边界；
3. [`policy/working-contract.md`](../policy/working-contract.md)；
4. [contract.md](contract.md) 的完整连续性语义；
5. Skills 中的调用时机和角色规则；
6. 本索引中的概括性提示。

具体 CLI、环境和开发命令见 [README.md](README.md)。
