# 技术文字、代码注释与 AGENTS.md

## 1. 先为读者优化

Google 的开发者文档指南把目标定为清晰、一致，并说明项目特定规范优先于通用风格指南（[About this guide](https://developers.google.com/style)）。写之前确定读者已有知识和正在完成的任务；删掉不能帮助该任务的信息。

通用写法：

- 用主动语态，明确谁执行动作；
- 条件放在指令之前，避免读者执行到一半才发现不适用；
- 步骤用编号列表，非顺序集合用项目符号；
- 链接文本描述目的，不使用一串“点击这里”；
- 日期使用无歧义形式，例如 `2026-10-30`；
- 截图只补充文字，提供 alt text，关键步骤不能只存在于图片。

这些要点来自 Google 的 [style highlights](https://developers.google.com/style/highlights)。中文可遵循项目自己的标点和语气，但仍应保持直接、具体、术语一致。

## 2. 代码注释：补充代码表达不了的信息

[Google C++ Style Guide 的注释章节](https://google.github.io/styleguide/cppguide.html#Comments)建议先用清晰名字让代码自解释，并明确说不要逐字描述显而易见的代码；更有价值的注释解释为什么这样做、非显然约束、可行方案为何没采用。

```ts
// 坏：把毫秒转换成秒。
const seconds = milliseconds / 1000;

// 好：上游签名协议只接受整数秒；向下取整避免签出未来时间。
const issuedAt = Math.floor(Date.now() / 1000);
```

值得就近说明：

- 外部协议、兼容性或安全约束；
- 反直觉顺序、锁范围、性能权衡；
- sentinel 值、单位、所有权、生命周期与副作用；
- 暂时不能消除的 workaround，并链接可追踪 issue。

注释与实现冲突时会误导读者，所以改变相关行为时同步更新；如果解释需要一篇设计文章，代码处写一句约束并链接 ADR/reference。

## 3. public API 的 docstring / doc comment

public API 的文档是调用者契约，应让调用者无需阅读实现即可正确调用。[Google Python Style Guide](https://google.github.io/styleguide/pyguide.html#383-functions-and-methods)要求 public API、非 trivial 或逻辑不明显的函数有 docstring，并描述调用语义而不是无关实现细节。

按语言生态的标准格式记录：

- 一句话说明用途；
- 参数的语义、单位、合法范围和默认行为（类型已表达的内容不重复）；
- 返回值及特殊状态；
- 调用者需要处理的错误；
- 可观察副作用、状态修改、所有权、线程/异步要求；
- 必要时给最短可运行例子。

不要写“`get_name` 返回 name”这类重复签名的 docstring。公开接口变化时，doc comment、reference、示例与版本兼容说明属于同一变更。语言或库的文档生成 API 会随版本变化，先用 Context7 MCP 的 `resolve-library-id`、`query-docs` 核对当前格式；需要临时 Python 工具时用 `uv run --with <package> ...`，不要把临时依赖写进项目。

## 4. AGENTS.md：给 coding agent 的项目事实

[agents.md](https://agents.md/)把 `AGENTS.md` 定义为给 coding agents 的 README：根目录提供项目上下文，大型 monorepo 可在子项目放更近的文件，离目标文件更近的说明优先。

建议只保留会改变 agent 行为、且无法从当前任务直接得知的项目事实：

- 一句话项目边界与主要组件；
- 真实的 setup、最小相关检查和完整验证命令；
- 非标准目录职责、生成文件或不可编辑区域；
- 项目特有命名、兼容、安全与数据约束；
- spec、ADR、runbook 和贡献规则的链接。

保持短小的原因不是任意行数门槛，而是上下文与过期风险：能从 package manifest、CI 或代码直接看出的依赖清单不要复制；“写好代码”“记得测试”这类通用建议不产生项目特定信息。绑定了 Lean Harness 的项目已经通过绑定文件导入 Harness 的规则入口，AGENTS.md 只补充本项目的事实，不复述 Harness 流程。

根文件写全局事实，嵌套文件只写该子树真正不同的命令或约束。agents.md 说明最近的文件优先，因此重复全局内容会制造冲突；避免复制，写差异即可。

不要放入：

- secrets、token 或个人机器绝对路径；
- 易变的类/函数清单；
- 尚未采纳的愿望与建议；
- 与仓库命令不符的示例；
- 对所有项目都成立的工程百科。

更新触发点：命令、目录责任、约束或权威文档位置改变时，在同一改动中更新对应 AGENTS.md。

## 5. 提交/CL 描述也是文档

Google 的 [CL descriptions](https://google.github.io/eng-practices/review/developer/cl-descriptions.html)指出，描述会成为长期公开记录，应说明主要变化是什么、为什么做，以及代码中看不出的决策或限制。第一行应能独立用于历史浏览与搜索；body 给问题背景、方案理由、已知不足和关联设计文档。

```text
fix(sync): preserve queued edits after reconnect

The reconnect path replaced the local queue before the server acknowledged it.
Merge acknowledged entries instead so offline edits remain retryable.
```

规范格式与 breaking-change 标注见 [decisions-and-releases.md](decisions-and-releases.md)。

## 来源

- https://developers.google.com/style
- https://developers.google.com/style/highlights
- https://google.github.io/styleguide/cppguide.html#Comments
- https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings
- https://google.github.io/eng-practices/review/developer/cl-descriptions.html
- https://agents.md/
