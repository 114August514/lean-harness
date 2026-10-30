# 代码评审：先看方向，再看细节

代码评审检查的是变更是否让系统更健康；它不替代测试、构建和静态检查。
先读变更说明并确认这件事值得做，再看核心设计；若方向或设计有根本问题，先反馈，
不要花时间逐行挑细节。这个顺序来自 Google 的
[评审导航](https://google.github.io/eng-practices/review/reviewer/navigate.html)。

## 评审前先看范围

一个易审的变更应是**一个自包含的变化**：只解决一件事，包含相关测试，合入后系统仍可正常工作，
并给出理解它所需的上下文。大小是概念判断，不是固定行数；文件分散度、生成代码、整文件删除都会
改变实际评审成本。若核心部分难以辨认，或无法在一次专注评审中理解，请作者按独立行为拆分；
功能变化与较大的重构通常分开，相关测试则与行为变化放在一起。
见 [Small CLs](https://google.github.io/eng-practices/review/developer/small-cls.html)。

拆分不能制造半成品：每个变更都应可独立合入，不破坏构建；新增 API 时同时给出一个真实用法，
避免先合入无法判断是否合适的闲置接口。

## 按这个顺序看

先浏览变更说明和文件清单，找到承载主要行为的文件；确认整体方向后，再按逻辑顺序覆盖其余文件。
以下顺序将高杠杆问题放在前面；一旦前项要求大改，先发反馈，再继续细节审查。
各项判据依据 Google 的
[What to look for in a code review](https://google.github.io/eng-practices/review/reviewer/looking-for.html)。

1. **设计**
   - 责任是否放在正确的模块，边界和依赖方向是否符合现有系统？
   - 仓库或成熟库是否已有能力可复用？这个功能现在是否确有必要？
   - 从完整文件和系统上下文看，变更是在降低还是累积整体复杂度？

2. **功能**
   - 实现是否满足契约和用户意图，而不只是作者描述的 happy path？
   - 检查边界、失败路径、状态转换，以及并发代码中的竞态和死锁风险。
   - 用户可见的 UI 行为仅靠 diff 难以判断时，要求可观察的演示或证据。

3. **复杂度**
   - 每行、函数、类型和调用接口能否被后续维护者快速理解和安全修改？
   - 删除只服务假想未来的参数、配置、抽象和泛化；不要用新 wrapper 掩盖错误边界。

4. **测试**
   - 测试层级是否与风险匹配，且与行为变更一起提交？
   - 断言是否针对可观察行为；实现出错时测试真的会失败吗？
   - 测试本身是否简单、确定、可维护，是否覆盖关键失败路径而非只覆盖成功路径？

5. **命名**
   - 名称是否准确表达领域概念和行为，并与仓库现有术语一致？
   - 若需要读实现才能猜出含义，优先改名，而不是补一段翻译式注释。

6. **注释**
   - 注释主要解释代码无法表达的“为什么”、约束或取舍，而不是复述“做了什么”。
   - 难懂代码优先简化；只有正则、复杂算法等确有必要时才解释机制。
   - 顺带检查旧注释、TODO 是否已失效或与新行为冲突。

7. **风格**
   - 以项目格式化器、lint 和既有 style guide 为准；个人偏好不得阻塞合入。
   - 大范围格式化与功能变化分开，避免遮蔽真实 diff、增加合并和回滚成本。

8. **文档**
   - 变更若影响构建、测试、使用、发布、公共接口或运维方式，应同步更新对应文档。
   - 删除或废弃行为时，也检查过期文档是否应删除或改写。
   - 具体文档规则与模板交给 `skill://project-docs`，这里仅检查一致性和影响覆盖。

除明确分工外，应读懂被分配审查的每一行人工代码；生成文件或大数据可按来源和生成方式抽查。
若缺少安全、隐私、并发、可访问性等专长，应明确未覆盖部分并补充合适审查者，而不是默认为通过。

## AI 编写代码的专项检查

先对照 [`policy/ai-failure-modes.md`](../../../policy/ai-failure-modes.md) 做一次定向扫描，
重点定位其中的**假测试 / Mock 自证、放宽或删除断言、吞噬异常、仓库内重复辅助函数**等条目；
检查方法和判定标准以该 policy 为准，不在这里复制第二套清单。若变更调用版本相关的库 API，
用仓库定义或 Context7 MCP（`resolve-library-id`、`query-docs`）核对真实签名，不凭模型记忆判断。

## 写可执行的评审评论

评论针对代码和后果，不评价作者；说明“哪里发生什么、为什么有风险、需要达到什么结果”。
Google 建议解释理由、标明严重度，并在指出问题与提供直接方案之间保持合适平衡：修复责任仍属于作者，
但有明确安全做法或项目惯例时应给出方向。
见 [How to write code review comments](https://google.github.io/eng-practices/review/reviewer/comments.html)。

沿用 `review-work` 的严重度，避免另造一套裁决语义：

- **BLOCKER**：不处理就不能接受；说明受影响的契约、用户结果或系统风险。
- **IMPORTANT**：当前变化应处理的重要问题；若允许后移，要明确由谁以什么方式承接。
- **OPTIONAL**：非阻塞改进或个人偏好；不得写成命令式必改项。

评论正文可借用 [Conventional Comments](https://conventionalcomments.org/) 的结构：

```text
<label> (<severity>): <具体问题>

<证据与影响：为什么>
<建议方向或完成条件>
```

常用 `issue`、`question`、`suggestion`：确认存在问题用 `issue`，尚不确定先用 `question`，
有改进方向用 `suggestion`。严重度与评论类型是两回事，例如：

```text
issue (BLOCKER): 失败后仍提交订单状态，违反“扣款与落单原子完成”的契约。

请让两个写入处于同一事务，并用失败路径测试证明任一步失败都不会留下订单。
```

```text
suggestion (OPTIONAL): 这里可复用现有 `parseCampusId`，减少第二套格式规则。

若本次不改，不影响合入。
```

不要只写“这里不好”“请重构”或只给替换代码：前者没有完成条件，后者隐藏了理由。
若作者只能在评审对话里解释复杂代码，通常应把代码改清楚；未来维护者看不到评审线程。

## 快速自检

- 是否先判断了变化本身和整体设计，而非从格式细节开始？
- 是否覆盖功能、复杂度、测试、命名、注释、风格和文档？
- 是否明确了自己未审的文件或专业领域？
- 每条评论是否有严重度、证据/影响、理由和可验证的完成条件？
- 是否把个人偏好标为 OPTIONAL，并避免重复机器检查？

## 来源

- https://google.github.io/eng-practices/review/reviewer/
- https://google.github.io/eng-practices/review/reviewer/navigate.html
- https://google.github.io/eng-practices/review/reviewer/looking-for.html
- https://google.github.io/eng-practices/review/reviewer/comments.html
- https://google.github.io/eng-practices/review/developer/small-cls.html
- https://conventionalcomments.org/
