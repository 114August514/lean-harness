# 结构化输出、版本与评估

## 1. 先把输出写成机器契约

当结果要进入程序分支、数据库或工具调用时，优先使用供应商原生 Structured Outputs / JSON Schema 或 function/tool calling，而不是要求“只返回 JSON”后再猜测格式。OpenAI 区分两种用途：连接应用功能时用 function calling；只需要结构化响应时用 JSON Schema 响应格式。[OpenAI Structured Outputs](https://platform.openai.com/docs/guides/structured-outputs)

Schema 要表达真实边界：

```json
{
  "type": "object",
  "properties": {
    "course_id": {"type": "string", "minLength": 1},
    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    "prerequisites": {
      "type": "array",
      "items": {"type": "string", "minLength": 1}
    }
  },
  "required": ["course_id", "confidence", "prerequisites"],
  "additionalProperties": false
}
```

- 列出全部必需字段；能拒绝未知字段时设 `additionalProperties: false`。
- 枚举、长度、数值范围能进 Schema 就不要只写在自然语言里。
- `null`、缺失、空数组表示不同状态时，明确选择一种语义。
- Schema 和本地类型应由同一事实源生成或做一致性检查，避免双份契约漂移。

具体 SDK 对 JSON Schema 的子集、拒绝响应、截断响应和 tool choice 支持不同；用 Context7 查询已安装 SDK 版本，不能凭记忆复制其他供应商的参数。

## 2. Schema 成功不等于结果可用

OpenAI Structured Outputs 保证受支持 Schema 的形状约束；OWASP 仍要求用确定性代码验证预期输出格式，并把模型输出当作潜在攻击面。[OpenAI Structured Outputs](https://platform.openai.com/docs/guides/structured-outputs) [OWASP LLM01:2025](https://genai.owasp.org/llmrisk/llm01-prompt-injection)

本地按顺序验收每个字段：

1. **传输状态**：超时、截断、拒绝、空响应、未完成状态先单独处理。
2. **语法与 Schema**：使用成熟 JSON 解析器和 schema/type validator；不要用正则“修 JSON”。
3. **字段语义**：日期真的可解析、ID 存在、引用能解析、字符串长度和字符集合理。
4. **跨字段不变量**：`start <= end`、百分比合计、互斥字段、父子关系无环等。
5. **权限与副作用**：模型给出的 tool name、资源 ID、路径和参数仍经过 allowlist、鉴权和业务检查。
6. **输出编码**：进入 HTML、SQL、Shell、日志时按目标上下文安全编码；结构化并不意味着可信。

校验失败返回类型化错误，例如 `refusal`、`truncated`、`schema_invalid`、`business_invalid`；这些类别决定“能否重试”，也让 eval 能定位回归。不要悄悄填默认值把缺字段伪装成成功。

### Knowledge Graph 实例

`~/Work/Knowledge_Graph/academic_kg_pipeline/llm.py` 有值得保留的做法：

- `JSONModelClient` 把 payload 与 `output_schema` 用 `json.dumps` 编码，而非拼接；
- tool 模式把 Schema 传给 Anthropic/OpenAI 的工具定义，并固定 `submit_result`；
- `parse_json` 至少拒绝非 JSON object；截断响应被显式报错；
- `ModelSettings.identity()` 集中给出协议、模型、输出模式、token 上限与 temperature。

但它还不是完整契约：`parse_json` 只检查顶层是 `dict`，tool input 也直接作为 `data` 返回，没有逐字段做本地 Schema 与业务校验。因此调用方不能仅凭“供应商接受了 Schema”就把 `ModelResult.data` 写入图谱。

## 3. Prompt、模型、参数共同组成身份

OpenAI 建议把生产应用固定到具体模型快照，并用测试/eval 监测 Prompt 或模型升级；当前指南也建议在代码中版本化 Prompt。[OpenAI Prompt Engineering](https://platform.openai.com/docs/guides/prompt-engineering)

每次可持久化结果至少记录：

```json
{
  "prompt_id": "course-extract",
  "prompt_version": "3",
  "prompt_sha256": "...",
  "schema_version": "2",
  "provider": "openai-compatible",
  "model": "provider-model-snapshot",
  "parameters": {"temperature": 0, "max_output_tokens": 4096},
  "input_sha256": "...",
  "created_at": "...",
  "usage": {"input_tokens": 0, "output_tokens": 0}
}
```

哈希使用**最终渲染前的稳定模板**还是最终请求，需项目统一；实用做法是模板哈希用于版本追踪，经过脱敏的输入哈希用于去重。不要记录 API key、Authorization header、完整秘密或本应删除的敏感输入。

版本变化规则：

- Prompt 文字、few-shot、Schema、模型快照或影响行为的参数变化，都视为行为候选变化。
- 版本号便于人读，内容哈希防止“同版本不同内容”；两者可以并存。
- 发布产物要能追到代码 revision；回滚应回到 Prompt + Schema + 模型配置的完整组合。

`~/Work/Knowledge_Graph/academic_kg_pipeline/ingestion/ocr_extractor.py` 的缓存 JSON 保存了 `model` 和时间，是良好起点；但缓存键只有 `course_id/page_no`，没有 prompt 哈希、模型版本、DPI 或源 PDF 内容哈希。修改 Prompt 或输入文件后可能误用旧结果，应把这些身份纳入缓存键/manifest，而不是只把它们写进 value。

## 4. 小型 golden set 先保护真实行为

Anthropic 要求 Prompt 工程开始前先定义成功标准和经验性测试；其 eval 指南要求测试贴近真实分布并包含边界。OpenAI 同样把 eval 视为模型升级和 Prompt 迭代的可靠性基础。[Anthropic Evaluation Guide](https://docs.anthropic.com/en/docs/test-and-evaluate/develop-tests) [OpenAI Evals Guide](https://platform.openai.com/docs/guides/evals)

项目初期不必先建庞大平台。保留一个小而有区分力的 golden set：

- 典型输入；
- 空、短、长、歧义、冲突、Unicode 等边界；
- 已发生过的失败；
- 拒绝/敏感输入；
- 带“忽略指令”等直接与间接注入内容的样本；
- 每例的期望结构、关键事实和允许变化范围。

评分从最确定的方法开始：

1. JSON Schema 与本地业务 validator；
2. exact match / 集合比较 / 数值容差等确定性评分；
3. 有明确 rubric 的人工或 LLM judge，用于无法机械判定的质量；
4. 同时记录 latency、token、成本、拒绝率和失败分类，避免只优化准确率。

LLM judge 也会变化，不能让它成为唯一真相；关键样本保留人工确认基线。

## 5. Prompt 或模型变更的回归比较

变更前先冻结 baseline 身份与结果；候选版本在**同一输入集和评分器**上运行，再比较：

- 总体指标与逐例 diff；
- 关键样本不能退化的硬门槛；
- 新增失败、拒绝、Schema/业务校验失败；
- p50/p95 latency、输入/输出 token 和估算成本；
- 多次运行的波动，尤其是非确定性任务。

不要只挑候选版本表现好的例子，也不要因为平均分上升就忽略高风险样本退化。OpenAI 建议在生产中固定模型快照；如果供应商只给滚动别名，就把实际返回的模型标识记录下来并提高回归频率。[OpenAI Prompt Engineering](https://platform.openai.com/docs/guides/prompt-engineering)

测试不得调用真实公网 API；仓库回归使用保存的 fixture/fake 验证渲染、解析、校验和错误路径。需要真实模型的 eval 是受控实验或发布检查，单独预算、脱敏并记录身份，不混入普通离线测试。

## 来源

- https://platform.openai.com/docs/guides/structured-outputs
- https://platform.openai.com/docs/guides/prompt-engineering
- https://platform.openai.com/docs/guides/evals
- https://docs.anthropic.com/en/docs/test-and-evaluate/develop-tests
- https://raw.githubusercontent.com/OWASP/www-project-top-10-for-large-language-model-applications/main/2_0_vulns/LLM01_PromptInjection.md
