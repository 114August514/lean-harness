# Lean Harness 架构

Lean Harness 是一套让 Agent 工作可恢复、可验证、可收敛的约定与参考实现。
它不建设平台级 Runtime，而是用尽量少的持久结构支撑长程工作。

## 顶层能力

```text
policy/          工作契约与决策边界（Agent 自主 / 升级的权威规则）
skills/          工作单元闭环：align → execute → verify → review → finish
continuity/      工作连续性：检查点、恢复日志、工作日志、上下文恢复
docs/            架构说明与项目产出的工作日志（docs/journal/）
adapters/        各 Runtime 的接入（OMP、Claude Code 等，后续工作）
```

## 信息来源的职责

工作连续性的核心原则是分离"可丢弃的运行信息"和"必须持久的事实"：

```text
模型上下文   → 可丢弃的运行信息
Issue / Spec → 目标、范围、验收和正式决定
Git commit   → 稳定工件检查点
恢复日志     → 最近检查点之后尚未稳定的执行现场（docs/journal/recovery/，gitignored）
工作日志     → Project 长程中按 Issue / Work Unit 分区的重要事件（docs/journal/work-log/，tracked）
PR           → Issue 中的一次交付与 Review 子范围
```

当前上下文由这些来源按需重新构造，不是另一份独立数据库。
完整语义见 `continuity/contract.md`。

## Skills 与连续性的分工

- **Skills** 判断：什么时候记录、哪些操作需要 `begin/end`、何时形成检查点、
  哪些事件值得进入工作日志、observation 对 Claim 的含义、最终状态。
- **连续性组件**（`continuity/`）负责：保存和读取记录、绑定 worktree、
  定位检查点、提供恢复事实、维护日志不变量。

连续性组件不做工作流编排，也不判断目标是否达成。

## 参考实现

`continuity/continuity/` 是一个 stdlib-only 的 Python 包，提供可运行入口
（`python -m continuity`）用于端到端验证。它只保证同一项目本地环境中的连续性，
不包含跨机器同步、远程日志服务、多存储后端或分布式一致性。
