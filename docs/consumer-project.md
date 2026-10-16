# 在项目中使用 Lean Harness 进行全流程软件开发

Lean Harness 是为 AI 编码时代设计的敏捷工程安全带（Harness）。它寄宿于 OMP、Claude Code 等 Agent 运行时，提供**“宏观定界、曳光打通、切片填充、测试自愈、Demo 交付”**的全流程支持。

---

## 一、 快速起步 (Getting Started)

### 场景 A：从 0 开始全新项目 (Greenfield)
使用 Harness 提供的内置脚手架工具，一键生成具备**开箱即用 Tracer Bullet 可运行骨架**、标准动词与双运行时绑定的新工程：

```bash
# 语法：./bin/new-project <目标路径> --stack <技术栈> [--runtime <omp|claude|all>]
./bin/new-project ~/Projects/my-app --stack python-uv --runtime all
cd ~/Projects/my-app

# 1. 验证基线健康状态
make doctor

# 2. 立即启动极简曳光弹 Demo
make demo

# 3. 运行开箱即绿的门禁自测
make check
```

**支持的技术栈适配器**：
- `python-uv`：Python 3.11+ / uv / ruff / pytest
- `ts-bun`：TypeScript / Bun / bun:test
- `go`：Go 1.21+ / gofmt / go test
- `rust`：Rust 2021 / cargo

---

### 场景 B：在已有项目中引入 Lean Harness (Brownfield)
若您已有代码库，只需进行一次轻量绑定：

```bash
cd /path/to/existing-project
/path/to/lean-harness/bind-project.sh . --runtime all --dev
```

绑定后会在项目中生成薄配置：
- `.omp/`：OMP 运行时配置，自动发现 Harness Skills；
- `.claude/skills/` 与 `CLAUDE.md`：Claude Code 运行时技能软链接与工程规则；
- 绝不侵入或修改您的业务源码。

---

## 二、 日常开发标准动词 (Standard Verb Interface)

开发者与 AI Agent 统一使用 Makefile 定义的标准动词进行交互，杜绝命令歧义：

| 标准动词 | 含义与执行时机 | 典型实现 / 底层调用 |
| :--- | :--- | :--- |
| `make check` | **[主门禁]** 提交代码前必跑（格式、Lint、全量测试） | `test lint fmt-check` |
| `make dev` | 启动本地服务或监视模式（曳光弹运行） | 本地热重载 / 启动入口 |
| `make test` | 快速运行单元与集成测试套件 | 本地轻量离线测试 |
| `make seed` | 预置真实业务语义的高保真初始种子数据 | `data/demo_seeds.json` |
| `make demo` | 一键装配种子数据并拉起交互式体验（附 30 秒玩转指南） | `seed && dev` |
| `make doctor` | 检查开发环境依赖、Git 基线与 Harness 完整性 | `./bin/doctor` |
| `make audit` | 自动扫描 Git Diff，排查删断言/吞异常/高危配置等 AI 失效模式 | `./bin/audit` |

---

## 三、 真实软件开发实战流程 (Real-World Development Flow)

### 阶段 1：需求塑形 (Shaping)
- 人类开发者花费 3 分钟，在 `docs/spec.md` 中填写：
  1. **唯一主旅程**：输入是什么，处理什么，期望输出什么；
  2. **明确非目标 (Non-goals)**：强制列出 3 条本次坚决不做的范围（防发散核心护栏）；
  3. **垂直切片清单 (Slice Backlog)**：将需求拆解为 2~4 个独立用户故事切片。

### 阶段 2：发射“曳光弹” (Tracer Bullet First)
- 在写业务逻辑之前，必须先让整个骨架“活起来”：
- 跑通 `make dev`，验证网络、依赖、基础入口完全打通。

### 阶段 3：垂直切片迭代与 TDD (Vertical Slices & TDD)
- **单切片推进**：Agent 每次只处理一个垂直切片；
- **先红后绿 (Fail-to-Pass)**：先写失败测试，亲眼见证它红，再写最小实现使其变绿；
- **切片级原子提交**：每个切片通过 `make check` 后，打勾 `docs/spec.md` 并立即 `git commit -m "feat(slice-N): ..."`。

### 阶段 4：通宵无人值守模式 (Overnight / Goal Mode)
当您开启 OMP 的 `--plan-yolo` 或 Claude Code 的 `/goal` 挂机睡觉时：
- **自愈熔断器**：单切片自愈修复上限为 3 轮，若仍无法修复，Agent 会自动回滚破坏性尝试，并在晨报中标记 `BLOCKED`，安全退出，避免死循环毁坏已有成果；
- **晨报交付物 (`docs/walkthrough.md`)**：Agent 自动生成晨报，记录昨晚完成的切片、`make check` 状态、1 分钟验货指南以及待决策事项。

### 阶段 5：Demo 验收与审查 (Demo & Review)
- 早晨醒来后，阅读 `docs/walkthrough.md`；
- 运行 `make demo`，按照控制台给出的 30 秒体验指南亲自上手验证；
- 运行 `make audit`，审查 Git Diff，合并完成交付。
