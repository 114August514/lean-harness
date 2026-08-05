---
name: investigate-question
description: 通过探索、比较、实验、benchmark、prototype 或分析减少有边界问题中的不确定性。两个正交维度：Intent（Explore/Evaluate/Test）和 Level（I0/I1/I2）。负面或不确定结果是有效交付。
---

# Purpose

通过探索、比较、实验、benchmark、prototype 或分析，减少有边界问题中的
不确定性，产出可信答案、候选方向、方案权衡、被排除的方向或下一项决策依据。

`investigate-question` 负责调查的执行阶段。调查完成只表示"结论及其证据
可评审"，完成判断属于 `finish-work`。

# Use when

- 需要发现或收窄可能方向（Explore）；
- 需要比较已知候选方案（Evaluate）；
- 需要验证一个明确假设（Test）；
- benchmark、性能实验、模型或算法评估、数据分析、可行性 prototype。

# Do not use when

- 目标已经是交付持久变化——用 `implement-change`（prototype 若需长期保留
  也属于它）；
- 目标是解释并修复异常行为——用 `debug-problem`；
- 没有明确的问题或探索目标，也没有完成边界——先收敛出可判断完成的
  调查目标，否则结果无法评审。

# Inputs

- Work Unit Contract（含 Investigation extension：Intent、
  Question or exploration objective、Search space、
  Baseline or comparison frame、Evidence standard、Validity threats、
  Exit criteria、Investigation level；存在具体决定时记录
  Decision supported）；
- 相关代码、文档、数据和既有结论。

# Process

1. **确认两个正交维度。**

   Intent——调查要产出什么：

   ```text
   Explore    发现和收窄可能方向
   Evaluate   比较已知候选方案
   Test       验证明确假设
   ```

   Level——结论要支撑多大代价的决定：

   ```text
   I0   Probe：快速方向探索或可行性探针，只支持局部或初步判断
   I1   Structured Evaluation：结构化探索、比较、benchmark 或普通工程评估
   I2   Systematic Investigation：支撑高代价或难逆转决定，
        需要更强方法、复现或 validity 控制
   ```

   两个维度自由组合：一次 Explore 可以是 I0 快速扫描，也可以是 I2 级别的
   系统性调研。

2. **按 Intent 组织调查。**
   - Explore：扫描、采样、构造最小探针。可以输出候选方向和下一步，
     不欠一个最终答案；
   - Evaluate：固定比较基准和对照条件，用同一 Evidence standard
     对待每个候选；
   - Test：先写清什么观测能证实或证伪假设，再执行。

3. **按 Level 控制证据强度。**
   - I0：速度优先，结论标注"初步"；
   - I1：结构化记录方法和数据，结论可被他人复核；
   - I2：显式处理 Validity threats（测量噪声、环境差异、样本偏差），
     提供复现所需的环境、参数和数据版本。

4. **如实报告负面和不确定结果。** "该方向不可行""假设未证实"
   "现有证据无法区分两个方案"都是有效交付，不得为追求正面结论
   而弱化或省略。

5. **降级与升级。** 可以自主降低调查强度（如 I1 降为 I0），前提是以下
   内容不变：

   ```text
   Question or exploration objective
   Decision supported
   Acceptance criteria
   Evidence standard（契约中约定的证据强度承诺）
   允许声明的结论范围
   ```

   降级会缩小决策用途、降低原定证据承诺或改变 Exit criteria 时，
   属于 Work Unit Contract 变化，必须经 `align-work` 确认。
   升级（如发现结论要支撑更高代价决定）同样调整契约并相应加强方法。

6. **交棒。** 达到 Exit criteria 或确认无法继续时，把结论、证据和
   剩余未知交给 `finish-work`。

# Delegation

- 扫描、数据收集、单个候选项的测量适合委派给 worker，工作包写明
  Questions、Search space 边界和 Evidence standard；
- 多个候选的并行评估可以分给不同 worker，但比较基准由主 Agent 统一给定，
  保证结果可比；
- 主 Agent 负责综合：交叉检查各 worker 的 Evidence，处理结论冲突；
- 委派格式见 `skills/_shared/delegation-contract.md`。

# Output

Investigation 的交付按 Intent 不同而不同，但至少包含：

```text
调查范围
已获得 Evidence
结论（Explore 可为候选方向）
被排除的方向
剩余未知
停止原因
下一步建议
```

负面或不确定结果同样按此结构交付。

# Completion and stop conditions

- 达到 Exit criteria：交棒给 `finish-work`；
- Explore 方向已收窄到可决策：交棒，不欠最终答案；
- 证据无法继续获得（环境、权限、成本限制）：如实交付剩余未知和
  停止原因，由 `finish-work` 判断 `DONE` / `BLOCKED` / `HANDOFF`；
- 调查揭示了新的独立问题：创建新 work unit，不在当前调查中扩张；
- 临时调查代码（探针、脚本、一次性 benchmark harness）默认不保留，
  按 `policy/working-contract.md` 的"临时工具"处理；调查结束即清理，
  不随交付提交。

# Related policy and references

- `policy/working-contract.md` — 实际推进、检查时机、临时工具；
- `policy/decision-boundaries.md` — 不确定性处理、范围变化；
- `skills/_shared/work-unit-contract.md` — Investigation extension 字段；
- `skills/_shared/delegation-contract.md` — 工作包与结果格式；
- `skills/_shared/work-lifecycle.md` — 调查在整个闭环中的位置。
