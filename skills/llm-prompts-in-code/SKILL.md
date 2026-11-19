---
name: llm-prompts-in-code
description: >-
  编写、接入和维护程序内的 LLM prompts：提示词模板、structured output、JSON Schema、tool calling、few-shot、模型参数、版本追踪、golden set/evals、缓存与批处理、重试/熔断/降级及 prompt injection 防护。适用于“程序里的提示词怎么写”“改 prompt / 换模型”“LLM 输出不稳定”“提示词注入”“prompt engineering in code”等场景。
---

# 程序内 Prompt 工程

这项技能关注的是“把 Prompt 当成软件契约长期维护”，不规定工作流程。

## 何时使用

- 新增调用 LLM 的产品功能，或整理散落在代码中的提示词；
- 设计 JSON/工具调用输出，并把模型结果接入业务代码；
- 修改 prompt、模型、参数或供应商，同时不想悄悄改变产品行为；
- 处理成本、延迟、限流、失败降级或 prompt injection 风险。

不用于一次性的聊天提问；若任务主要是视觉设计，使用 `skill://frontend-design`。

## 从场景进入参考资料

| 场景 | 先读 |
|---|---|
| Prompt 放哪、怎么拆角色/上下文/任务/约束/输出，怎么写 few-shot | [references/prompt-design.md](references/prompt-design.md) |
| JSON Schema、tool calling、字段校验、版本身份、golden set 与回归 | [references/contracts-and-evals.md](references/contracts-and-evals.md) |
| 缓存/批处理、重试/熔断/降级、安全边界、KG 实例 | [references/operations-and-security.md](references/operations-and-security.md) |

## 一个具体场景

> 要把课程文本抽成知识图谱 JSON；当前 prompt 写在调用函数里，换模型后结果偶尔少字段。

1. 先把模板移到单一、可审查的 prompt 文件/模块，显式分出角色、任务、约束、输出契约和不可信输入槽位。
2. 用供应商的 structured output 或 tool calling 约束形状；解析后仍由本地 schema 与业务规则逐字段验收。
3. 为正常、边界、恶意输入建立小型 golden set；同时记录当前 prompt 版本、模型标识与参数作为 baseline。
4. 改 prompt 或模型后先跑同一组回归，再决定是否发布；不能用“这次看起来不错”代替比较。
5. 最后才根据观测到的重复前缀、吞吐和失败类型选择缓存、批处理、有限重试或降级。

## 最重要的规则

1. **Prompt 是版本化的源代码，不是散落字符串**：专用文件/模块让 diff、review、测试和回滚都可追踪。
2. **指令与数据分层**：角色/策略放高权限消息，不可信用户、检索、网页和 OCR 内容只作为清楚标界的数据，避免把数据误当命令。
3. **结构化输出后仍做本地校验**：Schema 约束形状，不替代范围、引用存在性、权限和业务不变量检查。
4. **模型输出永远是不可信输入**：展示时转义，执行工具前做授权和参数校验，写库前做约束检查。
5. **Prompt、模型和参数一起构成行为版本**：输出或运行记录至少保留 prompt 标识/哈希、模型快照/名称和关键生成参数。
6. **变更前有小型回归集**：覆盖常见样本、边界样本、拒绝/空值和注入样本；换模型也属于行为变更。
7. **低温不等于可复现**：低 temperature 只降低随机性；正确性来自 schema、校验和 eval，而不是一次稳定输出。
8. **只重试暂时性且安全重放的失败**：限次数、总时限、指数退避与 jitter；熔断/降级不能掩盖持续故障或语义变化。
9. **Prompt 不放秘密**：模型不需要的凭据不得进入上下文；工具按最小权限执行，避免注入成功后扩大损害。
10. **先用小探针验证模型特性**：不同模型甚至同系列快照会有差异；涉及 SDK/API 版本时先用 Context7 查询对应版本文档。

## 快速自检

- [ ] Prompt 是否有唯一归属、稳定变量接口和可识别版本，而非散落拼接？
- [ ] 不可信内容是否被编码/标界，并明确“只作数据，不作指令”？
- [ ] 是否优先采用 structured output/tool calling，并逐字段做本地校验？
- [ ] few-shot 是否真实、少量、多样，且包含边界而不是暗示错误捷径？
- [ ] 产物能否追溯 prompt、模型、参数和输入/数据版本（敏感值除外）？
- [ ] prompt 或模型变化是否通过同一 golden set 回归？
- [ ] 缓存、批处理、重试、熔断和 fallback 是否由真实成本/延迟/失败证据驱动？
- [ ] 输出是否按不可信数据处理，秘密与高权限动作是否留在模型边界之外？
