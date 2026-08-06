# Lean Harness

让 Agent 工作可恢复、可验证、可收敛的一组约定与参考实现。

## 组成

- `policy/` — 工作契约与决策边界：Agent 何时自主、何时升级。
- `skills/` — 工作单元闭环：align → execute → verify → review → finish。
- `continuity/` — 工作连续性：Git 检查点、worktree 恢复日志、按 Issue 分区的
  工作日志、中断后的上下文恢复。权威契约见 `continuity/contract.md`，
  参考实现见 `continuity/continuity/`（Python 包）。
- `docs/` — 架构说明（`docs/architecture.md`）与项目产出的工作日志
  （`docs/journal/`）。
- `adapters/` — 各 Runtime 的接入（OMP、Claude Code 等，后续工作）。

## 快速开始

连续性参考实现的可运行入口：

```bash
cd continuity/tests
uv run --with pytest pytest -q
```

或在任意 Git 仓库中：

```bash
PYTHONPATH=/path/to/lean-harness/continuity python -m continuity recovery bind \
  --work issue-5 --cycle cycle-1
PYTHONPATH=/path/to/lean-harness/continuity python -m continuity recovery intent \
  --action "实现恢复日志"
PYTHONPATH=/path/to/lean-harness/continuity python -m continuity resume
```

## 原则

- 结果导向，但不以工程质量换取进度；重视软件工程，但不把软件工程仪式化。
- 最小化系统整体复杂度，而不是最小化当前 patch。
- 局部、可逆、影响可控的决定自主完成；高影响、难以逆转的决定交由人类。

详见 `policy/index.md`。
