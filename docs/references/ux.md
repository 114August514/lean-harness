# 技术专题：交互文案与 UX 提示规范 (UX Writing & Microcopy)

> 界面是代码的投影，文案是系统的声音。  
> **散值是机器可查的，视觉不协调不可查；同样，混乱的用词与恐吓式报错是代码失范，好的文案是把系统意图翻译成用户出路。**

本文档汇总 Google Material Design (Writing)、Microsoft Writing Style Guide、Mailchimp Content Style Guide、Command Line Interface Guidelines (clig.dev) 以及 Nielsen Norman Group (NN/g) 的核心规范，保留权威准则与原始公式，按**场景查阅式**组织。

---

## 查阅索引（按场景直达）

| 场景 / 痛点 | 查阅章节 | 核心规范与权威来源 |
|---|---|---|
| 报错拦截、异常提示、接口失败 | [一、错误与异常提示（Error Messages）](#一错误与异常提示error-messages) | NN/g 黄金三要素 + Microsoft 错误分级 |
| 物理删除、覆盖配置、不可逆操作 | [二、破坏性操作与二次确认（Confirmation Dialogs）](#二破坏性操作与二次确认confirmation-dialogs) | Microsoft 动词精准化 + 安全默认焦点 |
| 复制成功、已保存、轻量反馈 | [三、瞬时状态反馈（Toast / Snackbar）](#三瞬时状态反馈toast--snackbar) | Google Material 瞬时反馈与非阻塞原则 |
| 初始页面、无搜索结果、清空后 | [四、空状态与首次引导（Empty States）](#四空状态与首次引导empty-states) | Material & Mailchimp 解释+主行动原则 |
| 输入框、Label、占位符、行内校验 | [五、表单校验与输入辅助（Form & Inline Validation）](#五表单校验与输入辅助form--inline-validation) | Microsoft 占位符禁忌 + 就近报错原则 |
| 终端脚本、CLI 输出、日志反馈 | [六、CLI 终端交互文案（Command Line Interface）](#六cli-终端交互文案command-line-interface) | clig.dev 标准流隔离与 `[y/N]` 规范 |
| 纠结“确定/确认”、“删除/移除” | [七、高频交互动词与术语统一度量表（Glossary）](#七高频交互动词与术语统一度量表glossary) | 业界通用标准词典与语义边界 |
| 把握文案口吻、避免抖机灵翻车 | [八、语气光谱与同理心（Voice & Tone）](#八语气光谱与同理心voice--tone) | Mailchimp 动态语气矩阵 |
| 提交前自查代码与文案合规 | [九、文案合规自查清单（Checklist）](#九文案合规自查清单checklist) | 标点、大写、代码隔离、CI 规则 |

---

## 一、错误与异常提示（Error Messages）

权威来源：*Nielsen Norman Group (NN/g) Usability Heuristics #9* & *Microsoft Writing Style Guide*

### 1. 错误处理四大可用性原则（NN/g 核心准则）
1. **Explicit indication（明确指示）**：清楚告知发生了什么，严禁用“出错了”、“网络异常”等模糊词汇。
2. **Human language（人类语言）**：使用用户认知维度的自然语言，禁止原始堆栈、SQL 异常、空指针等技术黑话直接暴露。
3. **Never blame the user（不责怪用户）**：去除攻击性词汇（禁止“你输入了错误数据”、“你没有权限”；改用客观表述“格式不匹配”、“需要管理员权限”）。
4. **Constructive advice（建设性出路）**：必须提供可执行的恢复路径或替代方案。

### 2. 黄金三要素公式
```text
错误信息 = [现状] 发生了什么 + [原因] 为什么发生 + [出路] 接下来怎么做
```

| 错误类型 | ❌ 严禁的写法（差） | ✅ 规范写法（优） |
|---|---|---|
| **鉴权/权限** | `403 Forbidden` / `你无权访问` | `无法查看该报表。当前账号无权限，请联系管理员（admin@example.com）申请权限。` |
| **网络中断** | `Network Error` / `请求失败，请稍后重试` | `无法连接到服务器。网络连接已断开，请检查网络后点击「重试」。` |
| **文件大小** | `上传失败！` / `文件过大！` | `无法上传该附件。文件大小（12.5MB）超过了 10MB 上限，请压缩后再试。` |
| **名称冲突** | `Duplicate key error` | `无法创建项目。名称「Project-A」已存在，请换一个名称。` |

### 3. 与契约解耦规则
* 前端必须根据项目的错误码 / 错误信封契约定义处中的 `code`（错误码）做分支，映射到集中管理的文案字典。
* **严禁在前端硬编码或正则匹配后端的 message 字符串**——message 是给人看的，随时会改，错误码才是机器契约。

---

## 二、破坏性操作与二次确认（Confirmation Dialogs）

权威来源：*Microsoft Writing Style Guide (Dialogs & Alerts)* & *Apple HIG (Alerts)*

### 1. 核心准则
1. **Action-specific button verbs（动词精准化）**：严禁使用毫无意义的“确定 / 取消”。按钮必须是明确的动作动词：“删除 / 取消”、“放弃更改 / 继续编辑”。
2. **Explain irreversible consequences（讲清不可逆后果）**：明确说明操作带来的不可逆后果（数据是否彻底清除、是否可恢复、关联数据受什么影响）。
3. **Safe default（安全默认焦点）**：默认焦点永远停在安全的“取消”上。高危按钮使用危险警示色（Danger Token）。

### 2. 标准双段模板
```text
标题：[动作动词] + [目标对象] + ？
正文：说明影响范围、不可逆性或关联级联后果。
按钮：[取消]（安全默认）  [动作动词]（警示色/高危）
```

* **规范示例**：
  * **标题**：`永久删除「2026年度预算.xlsx」？`
  * **正文**：`删除后，该文件及其全部历史版本将无法恢复。`
  * **操作项**：`[取消]`（默认焦点） `[删除]`（红色警示）

---

## 三、瞬时状态反馈（Toast / Snackbar）

权威来源：*Google Material Design (Snackbars)*

### 1. 核心准则
1. **Short and scannable（简短扫读）**：字数严格控制在 **10 个汉字**（或 3~5 个英文单词）以内。
2. **Punctuation rule（标点禁忌）**：Toast 末尾**严禁加句号**。
3. **Transient & non-blocking（非阻塞）**：持续时间 2~4 秒自动消失，不打断主流程，不遮挡关键交互区域。
4. **Never use for critical blocking errors（禁止承载阻断性错误）**：需要用户阅读思考并决策的严重报错，绝对不能使用自动消失的 Toast，必须用持久化的 Inline Alert 或 Dialog。
5. **Support Undo where applicable（优先支持撤销）**：针对软删除或移位操作，提供撤销动作。

* **规范示例**：
  * `已保存`
  * `链接已复制到剪贴板`
  * `已移至废纸篓 [撤销]`

---

## 四、空状态与首次引导（Empty States）

权威来源：*Material Design* & *Mailchimp Content Style Guide*

### 1. 核心准则
1. **Explain why it is empty（说明为什么空）**：解释当前为何没有内容（初次使用、筛选条件过严、还是内容已被清空）。
2. **Direct first action（提供主行动入口）**：空状态不是空白画板，它必须带有一个明确的行动按钮（Call-to-Action）。

### 2. 标准结构
```text
[图标 / 紧凑插画]
标题：暂无[资源名称] / 未找到匹配的结果
说明：说明原因，或引导用户如何生成第一条数据。
主操作按钮：[新建/创建/清空筛选]
```

* **规范示例（搜索为空）**：
  * **标题**：`未找到相关成员`
  * **说明**：`请检查拼写，或尝试使用工号重新搜索。`
  * **按钮**：`[清除筛选条件]`

---

## 五、表单校验与输入辅助（Form & Inline Validation）

权威来源：*Microsoft Style Guide (Inputs)* & *Material Design (Text Fields)*

### 1. 核心准则
1. **Placeholder is not a label（占位符不是标签）**：占位符输入即消失，绝不能代替字段 Label。占位符仅用于输入格式范例（如 `例：user@domain.com`）。
2. **Proactive helper text（前置辅助文本）**：格式规则应前置在输入框下方（如 `8-20 位，须包含大小写字母与数字`），而不是等用户输错才弹红字。
3. **Inline error proximity（就近报错）**：校验错误信息必须直接显示在对应输入控件的正下方，禁止在表单顶部弹一个笼统的“表单存在错误”。
4. **Trigger timing（触发时机）**：在失焦（`onBlur`）或表单提交（`onSubmit`）时触发校验，**严禁在用户刚输入第一个字符时就提示报错**。

---

## 六、CLI 终端交互文案（Command Line Interface）

权威来源：*Command Line Interface Guidelines (clig.dev)*

### 1. 核心准则
1. **stdout vs stderr separation（标准流分离）**：
   * 正常数据输出到 `stdout`。
   * 交互提示、警告、进度、排错信息输出到 `stderr`，防止污染管道（如 `cmd | grep`）。
2. **Prompt casing for defaults（大小写指示默认值）**：
   * `Do you want to continue? [Y/n]`：回车默认选择 Yes。
   * `Delete database? [y/N]`：回车默认选择 No（危险操作必须以大写 N 为默认值）。
3. **Non-interactive fallback（非交互模式降级）**：
   * 当检测到非 TTY（管道中）或带有 `-y / --yes / --quiet` 参数时，直接使用默认值，严禁阻塞等待输入。
4. **NO_COLOR compliance（遵循色彩标准）**：
   * 遵循 `NO_COLOR` 环境变量。当输出重定向到文件或管道时，自动剥离 ANSI 彩色转义码。

---

## 七、高频交互动词与术语统一度量表（Glossary）

权威来源：*Microsoft Terminology Collection* & 业界通用前端词汇标准

全项目必须保持统一，严禁混用：

| 标准动词 | 严禁混用的词 | 语义边界与适用场景 | 英文对应 |
|---|---|---|---|
| **保存** | 保存一下、提交、存储 | 保存当前表单、草稿或配置改动 | Save |
| **提交** | 确定、发送、保存 | 表单校验通过并正式发送给服务端处理 | Submit |
| **确定** | 确认、好的、OK、Yes | 普通非危险确认、信息阅读完毕 | Confirm / OK |
| **删除** | 移除、清理、抹除 | 物理删除、永久销毁、不可恢复 | Delete |
| **移除** | 删除 | 解除绑定、移出当前列表，底层数据依然保留 | Remove |
| **重置** | 恢复默认、清空、重设 | 将表单或配置恢复至初始默认状态 | Reset |
| **取消** | 放弃、关闭 | 中止当前未完成的流程，不保存任何改动 | Cancel |
| **导出** | 下载、保存为 | 将系统内数据转换为特定格式文件并导出 | Export |
| **启用 / 停用** | 开启/关闭、打开/关闭 | 针对开关、功能模块、账号状态的切换 | Enable / Disable |

---

## 八、语气光谱与同理心（Voice & Tone）

权威来源：*Mailchimp Content Style Guide (Voice & Tone Framework)*

> **Voice is constant, Tone adapts.**（产品的基本声音始终是专业、坦诚、可信的；但语气需随情境动态调节。）

| 用户所处情境 | 语气基调 | 表现准则 | ❌ 严禁的反模式 |
|---|---|---|---|
| **流程顺利完成** | 清晰、轻快 | 用最少的字确认结果，不抢戏。如 `已发布`。 | 浮夸邀功（如“太棒了！您成功发布了！”） |
| **迷茫/首次探索** | 耐心、结构化 | 清晰引导步骤，降低心理门槛。如 `只需 2 步即可连接仓库...`。 | 甩出冷冰冰的文档链接不给解释。 |
| **遇到错误 / 故障** | **冷静、严肃、客观** | 客观说明原因，直接给解决办法。 | **严禁幽默、调侃、卖萌（严禁“哎呀~ 出错啦”、“Oops!”）**。在用户数据受损时幽默会激怒用户。 |

---

## 九、文案合规自查清单（Checklist）

在前端组件和页面提交前，对照自查：

- [ ] **错误有出路**：所有错误提示是否都包含“接下来怎么做”（重试/检查网络/联系人）？
- [ ] **无技术黑话**：是否隐藏了未捕获的底层异常（如 `undefined`、`500`、`NullPointer`）？
- [ ] **动词精准**：危险弹窗按钮是否是精准动词（`删除`），而非笼统的 `确定`？
- [ ] **标点合规**：Button、Tab、Toast、表单 Label 末尾**无任何句号**？
- [ ] **占位符规范**：Placeholder 是否仅用作格式示范，未代替 Label？
- [ ] **术语统一**：是否严格遵守第七节的统一动词表（未混淆“删除”与“移除”）？
- [ ] **契约解耦**：错误文案是否基于错误码（`code`）映射，而非匹配后端的 message 字符串？

---

## 十、权威来源

如需深入求证极端边界场景或研读完整条目，可查阅官方原文：

* **Google Material Design (Writing)**：[查看官方原文](https://m2.material.io/design/communication/writing.html)
* **Microsoft Writing Style Guide (Error & UI)**：[查看官方原文](https://learn.microsoft.com/en-us/style-guide/welcome/)
* **Command Line Interface Guidelines (clig.dev)**：[查看官方原文](https://clig.dev/)
* **Mailchimp Content Style Guide (Voice & Tone)**：[查看官方原文](https://github.com/mailchimp/content-style-guide)

