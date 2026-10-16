# 防污染自进化与知识沉淀协议 (Self-Evolution & Anti-Poisoning Protocol)

本协议规范在 AI 协同软件开发中，如何安全地沉淀知识与经验，实现 Harness 与项目的持续进化，同时坚决杜绝 Prompt 污染 (Prompt Poisoning) 与规则膨胀 (Rule Bloat)。

---

## 一、 核心进化哲学：资产外显化与确定性门槛

> **核心原则**：代码与测试资产是最硬核的进化载体。人类与 Agent 的认知进化，必须优先沉淀在**“机器可判定的测试用例与自动化工具”**中，严禁随意向 Agent 的自然语言性格与 System Prompt 中追加碎片化、矛盾的规则。

---

## 二、 三层进化模型 (The 3-Tier Evolution Model)

```text
┌────────────────────────────────────────────────────────┐
│ Level 1: 确定性资产进化 (Deterministic Oracle Layer)     │
│  - 载体：伴生测试 (tests/)、种子数据 (data/demo_seeds)   │
│  - 机制：全自动 (Fully Automated)                      │
│  - 触发：修复 Bug 或新增切片时，必须编写 Fail-to-Pass   │
│          测试用例。测试通过后作为永久资产固化，零歧义。 │
├────────────────────────────────────────────────────────┤
│ Level 2: 高频失效模式进化 (Failure Patterns Layer)     │
│  - 载体：policy/ai-failure-modes.md                    │
│  - 机制：防污染 "2-Strike" 门槛 (Semi-Automated)       │
│  - 触发：同一类错误在不同切片或任务中重复出现 ≥ 2 次时，│
│          提炼一条不超过 2 行的条目，记录病灶与禁令。   │
├────────────────────────────────────────────────────────┤
│ Level 3: 工具链与脚手架反哺 (Tooling & Template Layer)  │
│  - 载体：templates/adapters/、Makefile、bin/           │
│  - 机制：监督合入 (Supervised Merge)                   │
│  - 触发：在实战中发现更优的构建参数、诊断逻辑或动词，    │
│          反哺到脚手架模板，让所有后续项目开箱受惠。    │
└────────────────────────────────────────────────────────┘
```

---

## 三、 自进化五大反污染铁律 (Anti-Poisoning Golden Rules)

### 1. 禁止自动篡改核心性格与主规则
- Agent **严禁**在运行时自主重写 `policy/always.md`、`skills/` 主说明或系统提示词；
- 运行时的自省（Reflection）只能作为当次任务上下文中的思考过程，严禁无审查地持久化到全局指令中。

### 2. “2-Strike”规则沉淀门槛 (The 2-Strike Rule)
- **单次偶发错误禁止新增规则**：人类和模型在单次编码中出现的偶然笔误（如拼错变量名、少导一个包），直接通过测试自愈修复，**绝不为其追加自然语言规则**；
- **2-Strike 判定**：只有当同一种系统性失误（如：连续两次在不同模块中误用手搓加解密、两次写出无断言的 Mock 测试、两次在测试中发起公网请求），才允许向 `policy/ai-failure-modes.md` 追加一条具体条目；
- **2 行极简限制**：每条新增反模式条目必须紧凑（1 行描述错误表现，1 行给出标准纠偏动作），禁止输出长篇大论。

### 3. 测试资产优先于自然语言规则 (Oracle Over Prompt)
- 能用测试断言（Assertion）、静态类型（Typecheck）或 Linter 规则锁定的边界，**绝对不要**写成 Prompt 文本让模型用概率去记忆；
- 只有无法被机械化检查的“架构意图”与“反模式警示”，才作为 Policy 留存。

### 4. 定期规则剪枝与垃圾回收 (Rule Pruning & GC)
- 每隔一段时间（或底层基础模型大版本升级时），应当审查 `policy/ai-failure-modes.md`；
- 若某条规则所防范的问题已经成为现代模型的天然常识，或已被项目静态分析工具原生拦截，**必须果断删除该规则**，为 Context 腾出空间，保持 Harness 的超轻量（Lean）状态。

### 5. 规则变更的切片提交隔离
- 严禁将政策（Policy）文件的修改混在业务功能的 Git Commit 中；
- 规则更新必须独立形成原子 Commit（例如 `docs(policy): record 2-strike anti-pattern for blind catches`），以便追踪审查与回滚。
