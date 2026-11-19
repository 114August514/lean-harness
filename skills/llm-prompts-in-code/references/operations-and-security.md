# 生产运行与安全

## 1. 先观测，再优化成本和延迟

至少按 `prompt_id/version + model` 聚合：请求数、成功/拒绝/校验失败、p50/p95 延迟、输入/输出 token、缓存 token、重试次数和估算成本。OpenAI 生产指南把成本概括为 token 数与单位 token 成本的函数，并建议基于任务在模型能力、速度和价格间选择。[OpenAI Production Best Practices](https://platform.openai.com/docs/guides/production-best-practices)

优化顺序通常是：

1. 删掉不影响 eval 的重复上下文和冗长输出；
2. 为任务选择通过质量门槛的最小/更快模型；
3. 对重复的稳定前缀使用供应商 prompt caching；
4. 对不需要即时结果的独立请求使用异步 Batch；
5. 再考虑并发和流式体验，不用并发掩盖慢或失控的请求。

每一步都比较质量、成本和延迟；“更短”或“更便宜”若让校验失败/重试增加，可能总成本更高。

## 2. Caching：身份完整，失效明确

OpenAI Prompt Caching 复用相同 Prompt **前缀**的计算，可降低开始响应前的处理时间和缓存输入价格；只有前缀匹配才可能命中，且命中并非保证。[OpenAI Prompt Caching](https://platform.openai.com/docs/guides/prompt-caching)

- 把稳定指令、tool/schema 和稳定示例放在前面，变量输入放后面；不要为追求命中率改变任务语义。
- 监控实际 `cached_tokens`、latency 和成本，不根据“已开启缓存”推断收益。
- 应用层结果缓存的 key 至少包含：输入内容哈希、prompt 哈希/版本、Schema 版本、模型标识、影响行为的参数，以及图像/OCR 的渲染参数。
- 只缓存已经完整校验的结果；失败、截断或空响应不能伪装成命中。
- 缓存需有数据保留与隔离策略；包含用户数据时，确认供应商缓存/保留条款和应用自己的删除义务。

`~/Work/Knowledge_Graph/academic_kg_pipeline/ingestion/ocr_extractor.py` 的逐页磁盘缓存减少重复 OCR，是好方向；但仅用 `course_id/page_no` 命名，源 PDF、Prompt、模型与 DPI 变化不会失效，而且读取时只检查 `content` 非空。改进应是身份完整的 manifest/key + 输出校验，而不是再增加一个“清缓存”人工步骤。

## 3. Batching：只给可等待、彼此独立的工作

OpenAI Batch API 面向无需即时响应的异步请求，并明确列出 eval、大数据分类和 embedding 等场景；结果用每请求唯一 ID 关联。[OpenAI Batch API](https://platform.openai.com/docs/guides/batch)

适合：离线抽取、夜间 eval、批量分类。避免：交互式聊天、依赖前一结果的链式步骤、需要立即取消的操作。

批处理仍需：

- 每项稳定 `job_id` / 幂等键，不能依赖返回顺序；
- 每项独立状态、Schema/业务校验和可重放记录；
- 限制单批大小与总 token，局部失败只重放失败项；
- 记录所用 prompt/model 身份，因为一个 batch 也是一次行为版本运行。

## 4. Retry、Circuit Breaker 与 Fallback 各管不同问题

OpenAI 限流指南建议仅对暂时性错误遵守 `Retry-After`，缺失时使用带 jitter 的指数退避，并限制尝试次数和总时长；quota、billing 等需人工处理的错误不应重试。若 SDK 自带重试，要计入总预算，避免嵌套重试倍增请求。[OpenAI Rate Limits](https://platform.openai.com/docs/guides/rate-limits)

重试前同时满足：

- 错误被分类为暂时性，如部分 `429/503`、连接中断；
- 操作安全重放，或有幂等键；流式响应已产生部分副作用时不能盲目重放；
- 仍在调用方 deadline、次数和成本预算内。

Prompt 违反 Schema、业务校验失败或模型持续拒绝，通常先暴露为产品/契约问题；不要用无限“再问一次”掩盖。

Circuit Breaker 用于依赖持续失败时停止反复调用，和 Retry 的目的不同。标准状态是 closed → open → half-open；open 期间快速失败，冷却后只放少量探针恢复。[Microsoft Circuit Breaker Pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/circuit-breaker)

Fallback model 只在产品允许降级时使用，并且：

- fallback 必须支持同一输入/输出契约并通过自己的 golden set；
- 输出明确记录实际模型，监控降级率；
- 若质量/安全能力不同，宁可返回可解释的暂时不可用，也不要静默给出较差结果；
- fallback 不能绕过原模型的拒绝、安全策略或权限控制。

`~/Work/Knowledge_Graph/academic_kg_pipeline/llm.py` 已有有限重试、`CLOSED/OPEN/HALF-OPEN` 状态和备用模型，并用 `ModelSettings` 集中配置，这是可复用方向。需要警惕：退避是固定指数上限但无 jitter，fallback 的实际身份没有进入 `ModelResult`，而且广泛捕获异常后可能把契约错误也触发为切流。生产实现应按错误类型触发，并把降级事实放进结果元数据。

## 5. Prompt Injection：隔离影响，而非相信提示词能防住

OWASP LLM01:2025 区分直接注入和来自网页、文件等外部源的间接注入，并指出 RAG 或 fine-tuning 不能完全消除该风险；建议约束模型行为、验证输出、最小权限、隔离外部内容和高风险动作人工批准。[OWASP LLM01:2025 source](https://raw.githubusercontent.com/OWASP/www-project-top-10-for-large-language-model-applications/main/2_0_vulns/LLM01_PromptInjection.md)

防护分层：

1. **数据边界**：用户/RAG/网页/OCR/工具结果作为标明来源的不可信数据，不进入 system/developer 指令。
2. **能力边界**：模型只得到完成任务所需的工具和数据；资源级权限在服务端按真实用户校验。
3. **动作边界**：删除、付款、发送、发布等高风险动作要求确定性校验和必要的人类确认。
4. **输出边界**：模型输出进入浏览器、SQL、Shell、文件路径或工具前做上下文相应的验证/编码。
5. **测试边界**：golden set 加入直接、间接、混淆和多模态注入；监控成功/拦截与异常工具调用。

XML/JSON 分隔会提高可辨认性，但不能证明安全；真正限制损害的是应用层权限和校验。

## 6. Secrets 与敏感数据不进入 Prompt

OWASP LLM02:2025 将凭据、个人、财务、健康和机密业务数据列为敏感信息，并提醒 system prompt 限制可能被注入绕过；应使用最小权限、输入清理和明确的数据保留政策。[OWASP LLM02:2025 source](https://raw.githubusercontent.com/OWASP/www-project-top-10-for-large-language-model-applications/main/2_0_vulns/LLM02_SensitiveInformationDisclosure.md)

- API key 只放 secret manager/环境注入与 Authorization header，不放 Prompt、few-shot、日志、错误或 eval fixture。
- 在请求前做数据最小化/脱敏；模型不需要的字段不要发送。
- 不把 system prompt 当秘密保险箱；真正的秘密应根本不在模型上下文。
- 日志记录哈希、长度、分类和 request ID 即可时，不保存完整输入输出。

KG 两个实例都把 key 放 HTTP header 而不是 Prompt，这是正确边界；但异常/日志和缓存仍要避免落下完整敏感内容。

## 7. 模型输出一律视为不可信

OWASP LLM05:2025 指出，未验证的模型输出进入下游可能造成 XSS、SSRF、提权或代码执行；建议像处理用户输入一样做 zero-trust 验证，并按 HTML、SQL 等目标上下文编码。[OWASP LLM05:2025 source](https://raw.githubusercontent.com/OWASP/www-project-top-10-for-large-language-model-applications/main/2_0_vulns/LLM05_ImproperOutputHandling.md)

因此不要：

- `eval` / `exec` 模型文本；
- 直接执行模型生成的 Shell/SQL 或把它拼进路径/URL；
- 未转义渲染 Markdown/HTML；
- 让模型返回“已授权”就跳过鉴权；
- 自动安装模型臆造的包名。

应使用参数化 SQL、allowlist 工具、规范化后再校验的路径、输出编码和沙箱；高权限调用由应用代码决定。Structured Output 只让恶意/错误数据更易解析，不会把它变可信。

## 来源

- https://platform.openai.com/docs/guides/production-best-practices
- https://platform.openai.com/docs/guides/prompt-caching
- https://platform.openai.com/docs/guides/batch
- https://platform.openai.com/docs/guides/rate-limits
- https://learn.microsoft.com/en-us/azure/architecture/patterns/circuit-breaker
- https://raw.githubusercontent.com/OWASP/www-project-top-10-for-large-language-model-applications/main/2_0_vulns/LLM01_PromptInjection.md
- https://raw.githubusercontent.com/OWASP/www-project-top-10-for-large-language-model-applications/main/2_0_vulns/LLM02_SensitiveInformationDisclosure.md
- https://raw.githubusercontent.com/OWASP/www-project-top-10-for-large-language-model-applications/main/2_0_vulns/LLM05_ImproperOutputHandling.md
