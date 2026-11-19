# 决策、版本与变更历史

## 1. 什么时候写 ADR

[ADR 定义](https://adr.github.io/)是一份捕捉单个重要设计决定及其理由的记录。选择会影响系统结构、非功能属性、依赖、接口或构建方式，并且未来的人可能合理地质疑“为什么这样做”时，写 ADR。

适合记录：

- 数据所有权、模块边界、同步/异步通信方式；
- 数据库、框架、协议或关键依赖的选择；
- 安全、可靠性、性能要求带来的结构性取舍；
- public API 或迁移策略中难以逆转的决定。

通常不用 ADR：可由局部代码显然表达的实现细节、纯格式偏好、临时实验、尚未形成决定的会议流水账。是否重要看后果与反悔成本，不看代码行数。

## 2. 一份 ADR 写什么

Michael Nygard 的[原始格式](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)包含 Title、Context、Decision、Status、Consequences；[MADR](https://adr.github.io/madr/)在此基础上提供精简的 Markdown 结构。实用的最小集合是：

1. **标题**：短句说清做出的决定；
2. **状态和日期**：proposed / accepted / rejected / superseded；
3. **背景与问题**：当时的约束和相互冲突的力量，保持事实性；
4. **备选方案**：只列真正考虑过的选项及关键权衡；
5. **决定**：选了什么，为什么符合驱动因素；
6. **后果**：正面、负面与中性后果，以及如何确认决定已落地。

一份文件只写一个决定，采用 `NNNN-short-title.md` 这类单调递增编号便于稳定引用；MADR 也采用该文件名模式。决定被替代时保留旧记录、标为 superseded 并链接新 ADR，因为旧上下文仍解释已有系统；Nygard 明确建议不要复用编号或抹去旧决定。

坏例子：`选择 PostgreSQL，因为它最好。` 这没有背景、比较标准或代价。

较好例子：`在需要事务一致性、团队已有运维能力且首年数据量可由单实例承担的背景下，选择 PostgreSQL；代价是离线开发需要本地实例，跨区域写入另行评估。`

## 3. CHANGELOG 写给谁

CHANGELOG 面向使用者和集成者，回答“从上一版升级会发生什么”。[Keep a Changelog](https://keepachangelog.com/en/1.1.0/)明确反对把 Git log 原样倾倒成 changelog，并建议：

- 顶部保留 `Unreleased`，发布时把条目移入版本节；
- 版本按倒序排列，日期采用 `YYYY-MM-DD`；
- 按 Added、Changed、Deprecated、Removed、Fixed、Security 分类；
- 只写 notable changes，用用户能理解的影响描述；
- 版本标题链接 release/tag，必要时提供版本间 compare 链接。

```markdown
### Fixed
- 导入失败后不再留下无法删除的空项目。
```

优于：

```markdown
### Fixed
- 修改 `Importer.finalize()`。
```

前者说明使用者可观察的结果。内部重构若不改变使用者行为，通常无需进入 CHANGELOG；安全修复是否披露细节应服从项目的安全发布策略。

## 4. SemVer 的前提和含义

只有先声明清楚 **public API**，语义版本才有可解释性；这是 [SemVer 2.0.0](https://semver.org/) 的第一条要求。public API 不仅是函数，也可能是 CLI 参数、配置格式、网络协议、事件 schema 或用户依赖的文件格式；项目应明确自己把哪些界面纳入兼容承诺。

对于已进入稳定版本的 `MAJOR.MINOR.PATCH`：

- 不兼容 public API 变化：升 MAJOR；
- 向后兼容的 public API 功能新增或弃用：升 MINOR；
- 向后兼容的缺陷修复：升 PATCH。

发布过的版本内容不应被原地替换，应发布新版本。`0.y.z` 表示初始开发，public API 不被视为稳定；这不等于可以不说明破坏性变化。pre-release（如 `1.2.0-rc.1`）优先级低于对应正式版，`+build` 元数据不参与版本优先级。

不要把“改动很多”直接等同于 MAJOR，也不要仅从 commit 类型猜版本：最终依据是已声明 public API 的兼容影响。

## 5. Conventional Commits

采用 [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/) 时，格式是：

```text
<type>[optional scope][!]: <description>

[optional body]

[optional footer(s)]
```

- 新功能用 `feat`，缺陷修复用 `fix`；其他类型可由项目约定，但要保持小而稳定的集合。
- scope 是可选的代码域名词，如 `feat(import): ...`。
- `!` 或 `BREAKING CHANGE: ...` footer 表示破坏性 API 变化；footer 应说清迁移影响。
- body 补充标题无法表达的背景、为什么采用此方案、限制和关联 issue。

Google 的 [CL description 指南](https://google.github.io/eng-practices/review/developer/cl-descriptions.html)要求描述能独立说明 **what** 与 **why**，因为它会成为长期版本历史。标题 `fix: fix bug` 没有检索价值；应写成 `fix(import): remove partial project after parse failure`，body 再解释根因与取舍。

Conventional Commits 可以驱动自动化，但不能替代 CHANGELOG：commit 面向维护历史，CHANGELOG 经过筛选并面向版本使用者。自动生成后仍应按用户影响编辑。

## 来源

- https://adr.github.io/
- https://adr.github.io/madr/
- https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions
- https://keepachangelog.com/en/1.1.0/
- https://semver.org/
- https://www.conventionalcommits.org/en/v1.0.0/
- https://google.github.io/eng-practices/review/developer/cl-descriptions.html
