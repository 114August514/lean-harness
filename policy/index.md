# Lean Harness Policy 索引

本文件是 Lean Harness policy 的常驻入口。

详细规则以以下文件为准：

- [工作契约](working-contract.md)
- [决策边界](decision-boundaries.md)

## 核心原则

- 推进真实、可验证的结果，不用流程冒充进度。
- 最小化系统整体复杂度，而不是最小化当前 patch。
- 不为假设中的未来提前建设，也不向现有模块无限增量堆叠。
- 设计与实现一起演进；真实边界出现时允许局部结构调整。
- 兼容真实依赖，迁移真实状态，不兼容开发过程。
- 检查由风险和决策价值触发，不机械提前或重复执行。
- 默认要求获得证据，不默认要求新增永久测试。
- 临时施工工具不默认成为仓库长期能力。
- 局部、可逆、影响可控的决定自主完成。
- 高影响、难以逆转或涉及真实外部义务的决定交由人类。
- 没有 fresh evidence 时不得宣称 `DONE`。

## 按需阅读

开始非 trivial 实现或发现模块持续膨胀时，阅读：

- `working-contract.md` 的“简单性与工程质量”
- `working-contract.md` 的“持续设计”
- `working-contract.md` 的“结构判断”

涉及内部接口重构、旧实现、fallback、版本或 migration 时，阅读：

- `working-contract.md` 的“开发收敛”
- `working-contract.md` 的“兼容与迁移”
- `decision-boundaries.md` 的“兼容与迁移决策”

准备运行测试、构建、扫描或 review 时，阅读：

- `working-contract.md` 的“检查时机”
- `working-contract.md` 的“测试与验证”
- `decision-boundaries.md` 的“测试与验证决策”

准备添加脚本、CLI、检查器或自动化工具时，阅读：

- `working-contract.md` 的“临时工具”
- `decision-boundaries.md` 的“临时工作手段”

准备改写 Git 历史、强制删除 branch / worktree 或清除本地修改时，阅读：

- `decision-boundaries.md` 的“本地破坏式状态操作”
- `decision-boundaries.md` 的“未明确授权时禁止执行”
- [`../git/contract.md`](../git/contract.md) 的“安全清理”和“Destructive operations”

不确定是否需要询问人类时，阅读：

- `decision-boundaries.md` 的“默认决策规则”
- `decision-boundaries.md` 的“必须请求人类决定”
- `decision-boundaries.md` 的“未明确授权时禁止执行”

准备宣称完成或停止时，阅读：

- `working-contract.md` 的“完成语义”
- `decision-boundaries.md` 的“BLOCKED 判定”

## 优先级

发生冲突时，按以下顺序处理：

1. 当前任务明确目标和验收条件；
2. `decision-boundaries.md` 中的安全、外部契约和禁止边界；
3. `working-contract.md`；
4. 本索引中的概括性提示。

本索引不替代详细规则。
