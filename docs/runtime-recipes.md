# 运行时协同与长程无监督运行配方 (Runtime Recipes)

Lean Harness 作为工程外骨格，本身不捆绑特定的 LLM 客户端，而是寄宿在成熟的运行时（如 OMP、Claude Code、Antigravity）之上。

本指南提供在主流运行时中如何结合 Lean Harness 规则与物理门禁，安全启动**长程无监督运行（Overnight / Unsupervised Loop）**的实战配方。

---

## 配方一：Antigravity 中的 `/goal` 模式（最省心）

### 适用场景
在 IDE 或对话界面中，需要 Agent 自动完成一个耗时较长、涉及多处改动的完整任务，期间你不想被细枝末节打扰。

### 触发方式
在输入框中直接输入：
```text
/goal <任务目标与非目标>
```

### 推荐 Prompt 模板
```text
/goal 实现用户两步验证 (2FA) 接口：
1. 目标：生成 TOTP 密钥与验证 6 位验证码接口；
2. 非目标：不修改数据库现有 User 表，不引入新的重型依赖，使用成熟的 pyotp/otp 库；
3. 验证：必须为正常路径与防重放/防爆破异常路径编写测试，运行 make check 确保全部绿灯；
4. 完成条件：make check 和 make audit 均无报错，并输出简要 Git Diff。
```

### 运行机制
- Antigravity 自主循环调度引擎负责维持多轮对话与工具调用；
- Lean Harness 的 `policy/always.md` 强制 Agent 先红后绿编写真实测试；
- 物理真理基准 `make check` 会阻止 Agent 在测试未通过时提前宣称完成。

---

## 配方二：OMP 终端全自动无人值守（CLI 原生）

### 适用场景
在远程开发机、服务器或后台终端（`tmux` / `nohup`）中挂机执行任务。

### 1. Plan-Yolo 模式（最推荐：先自动规划，再自动执行）
```bash
omp --plan-yolo "阅读 docs/spec.md，实现库存扣减垂直切片，确保 make check 全绿"
```
* **行为**：OMP 会首先进入只读 Plan 模式进行全局架构与代码上下文推理；在给出首份清晰方案后，自动确认并转入实现模式，无缝完成代码与测试编写。

### 2. Auto-Approve 模式（极速执行）
```bash
omp --auto-approve "修复 Issue #108 订单幂等性 Bug，遵循先红后绿测试"
```
* **行为**：跳过所有 Bash 执行与文件编辑的人工确认弹窗，依靠本地 `make check` 拦截错误，适合中小型缺陷修复。

### 3. 后台守护与会话管理
OMP 内置了进程守护能力：
```bash
# 查看后台运行的 Agent 任务
omp ps

# 任务完成后，提取当前会话的上下文与耗时统计
omp stats
```

---

## 配方三：Claude Code 终端自主流

### 适用场景
使用 Anthropic 官方 `claude` 终端工具进行配合作业。

### 1. 项目挂载
确保当前项目已执行：
```bash
/path/to/lean-harness/bind-project.sh . --runtime claude --dev
```
此命令已在当前项目根目录生成 `CLAUDE.md` 并软链了 Lean Harness 的 Skills。

### 2. 启动与执行
直接启动 `claude`：
```bash
claude "按照 CLAUDE.md 中的规则，为支付模块添加 Webhook 验签逻辑，提交前跑通 make check"
```
* Claude Code 会自动读取 `CLAUDE.md` 中的底线规则：
  - 先搜再写（`git grep`）；
  - 测试先行（先红后绿）；
  - 严禁手搓加密基础设施；
  - 宣称完成前必须通过 `make check`。

---

## 三、 长程无监督运行的避坑自检清单

在关掉电脑去睡觉或离开工位前，花 30 秒核对这 3 点：

- [ ] **是否已处于独立分支或 Worktree 中？**  
  绝不要在 `main` 分支上直接挂机跑无监督任务。先开分支：`git checkout -b task/overnight-refactor`。
- [ ] **`make test` 当前是否本来就是绿的？**  
  在启动长程任务前，先确认当前基线健康，避免让 Agent 去排查原本就坏掉的历史债务。
- [ ] **是否写明了明确的 Non-goals（非目标）？**  
  一句话告诉 Agent “不要碰什么”，可以节省 80% 不必要的发散改动。
