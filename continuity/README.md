# continuity — 工作连续性

`continuity` 是 Lean Harness 的顶层工作连续性能力。它保存和组合恢复事实，
不判断 Claim、Acceptance、DONE 或下一项产品决策。

Agent 的常驻入口与按需阅读导航见 [`index.md`](index.md)，权威完整语义见
[`contract.md`](contract.md)。本 README 只说明实现布局、运行方式和开发命令。

参考实现使用三类来源：

- Project-shared Work Log：GitHub Issue 中带稳定标记的结构化 event comment；
- Local Recovery Log：`<git-common-dir>/lean-harness/recovery/<worktree-id>/`；
- Git / Issue / PR facts：恢复时实时读取。

共享事件不会写入 checkout，也不属于某个 branch、worktree 或 PR。Recovery Log
只属于当前 clone 和 worktree，不会进入 Git，也不会冒充跨协作者同步。

目录布局：

```text
continuity/
├── continuity/   # Python implementation package
├── tests/        # scenario and unit tests
├── index.md      # Agent entry and progressive-disclosure routing
├── contract.md
└── README.md
```

## 可执行入口

进入本 module 后运行：

```bash
cd continuity
uv run python -m continuity --help
uv run python -m continuity recovery status
uv run python -m continuity shared list --work issue-5
uv run python -m continuity shared find --work issue-5 --event-id evt-...
uv run python -m continuity shared unresolved --work issue-5
uv run python -m continuity shared latest-checkpoint --work issue-5 --cycle cycle-1
uv run python -m continuity resume --work issue-5 --cycle cycle-1
```

uv 只管理 Python 版本、测试和 lint 工具；本 module 不是可安装 package，不使用
build backend，也不会生成 `.egg-info`。远端操作默认从 `origin` 推导 `owner/name`，也可用全局
`--repository owner/name` 显式指定。

### 发布共享事件

写入共享日志前必须先建立本地 binding：

```bash
uv run python -m continuity recovery bind --work issue-5 --cycle cycle-1
uv run python -m continuity shared append \
  --work issue-5 --cycle cycle-1 \
  --kind direction-changed --producer agent:example \
  --summary "Use GitHub Issue comments for the shared work log"
```

结构性事件使用专用命令：

```bash
uv run python -m continuity shared checkpoint \
  --work issue-5 --cycle cycle-1 --commit HEAD \
  --producer agent:example

uv run python -m continuity shared remap-checkpoint \
  --work issue-5 --cycle cycle-1 \
  --checkpoint-event evt-checkpoint --new-commit HEAD \
  --reason squash --producer agent:example
```

每次共享写入实际执行：

```text
event_id → local intent → local begin → Issue comment append
→ find(event_id) confirmation → local end
```

响应丢失后，replacement 先运行：

```bash
uv run python -m continuity shared reconcile
```

它只按 `event_id` 查询并补 `end`，不会自动重试。确认远端不存在后，才可显式
增加 `--retry-missing`。

## 本地恢复与轮转

```bash
uv run python -m continuity recovery intent --action "implement parser"
uv run python -m continuity recovery status
uv run python -m continuity recovery rotate \
  --checkpoint-event evt-checkpoint \
  --durable-events-confirmed \
  --next-phase verification
```

rotation 会验证共享 checkpoint 的 work / cycle / resolved commit、当前 Git 路径、
structured dirty state、未解释的远端操作、长期事件确认和下一阶段。没有 `--force`。

## 验证

```bash
uv run pytest -q
uv run ruff check .
uv run python -m compileall -q continuity
uv run python -m continuity --help
```

测试使用真实 Git 仓库、linked worktree、冲突状态和两个完全独立的 clone；远端
共享日志由 deterministic fake 实现同一个窄 port。

## 明确不包含

Workflow Engine、Event Sourcing、Event Bus、后台同步、独立数据库、distributed
lock、provider registry、跨机器未提交 working tree 同步、自动验收和通用 retry。
