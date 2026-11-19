# 可访问性最低线与 UI 验收

## 可访问性最低线

WCAG 2.2 是可测试成功标准；WAI-ARIA APG 是复杂控件的设计模式与键盘约定。不要把“跑过自动扫描”写成“符合 WCAG”：自动工具覆盖不了阅读顺序、语义是否准确、焦点是否合理和任务能否完成。

### 1. 语义与名称

- 用原生 `button`、`a`、`input`、标题、列表和 landmark 表达真实用途。
- 每个输入都有可见 label；图标按钮也有能描述动作的 accessible name。
- 信息图片提供等价文本；纯装饰图片让辅助技术忽略。WCAG 1.1.1 要求非文本内容有等价替代，装饰内容是明确例外。
- 动态成功、等待、进度和错误若不取得焦点，用可被辅助技术识别的状态消息。

APG 明确提醒“No ARIA is better than Bad ARIA”：`role="button"` 是实现按钮键盘行为的承诺，role 本身不会提供这些行为。因此先用原生元素；确实没有原生模式时，按 APG 对应 pattern 实现 role、state、keyboard interaction，并在目标浏览器/辅助技术组合验证。

### 2. 键盘与焦点

WCAG 2.1.1 要求除依赖轨迹的自由手势外，功能都可通过键盘接口完成；WCAG 2.4.7 要求键盘焦点指示可见。

手工走一遍：

1. 只用 `Tab` / `Shift+Tab` 到达所有交互项，顺序与视觉/阅读顺序一致；
2. 原生按钮支持 `Enter` / `Space`，链接行为符合平台习惯；
3. 打开 dialog 后焦点进入合理位置，Tab 不逃出；关闭后焦点回到触发点；
4. 下拉、tabs、menu、combobox 等复杂控件使用 APG 对应键位；
5. 没有键盘陷阱，焦点不会无故丢到页面起点；
6. `:focus-visible` 不被全局 outline reset 隐藏。

拖拽、滑动等手势提供按钮、剪切粘贴或其他键盘等价路径。

### 3. 视觉与感知

- WCAG 1.4.3 AA：普通文本与背景至少 `4.5:1`，大号文本至少 `3:1`；不要四舍五入临界值。
- 不只用颜色表达错误、选中、涨跌或在线状态；再加文字、形状、图标或模式。
- 放大文本、窄视口、系统深浅色与高对比设置下，关键信息和动作仍可用。
- 动画尊重减少动态效果偏好；不要让自动消失成为读取关键内容的唯一机会。

### 4. 表单与错误

输入的 label/说明最低要求见 WCAG 3.3.2；自动识别的错误要用文字说明具体字段和问题，见 WCAG 3.3.1。错误边框和红色不能单独承担信息。详见 [界面状态与表单](ui-states-and-forms.md)。

## Agent 如何验收自己“看不见”的 UI

源码、类型检查和 DOM 断言都不能证明布局真实可用。Agent 应通过 OMP browser 获取真实渲染证据：

### 浏览器观察流程

1. **打开真实路由**：使用项目实际 dev server / preview，不用凭 JSX 想象结果。
2. **固定场景**：准备可复现数据，分别进入 loading、empty、error、success、partial；不要只截 happy path。
3. **截屏**：至少取产品支持的窄视口与桌面视口；再覆盖 dialog、长文本、字段错误、深色模式等受影响场景。
4. **读 accessibility tree**：检查 landmark、heading 层级、role、name、value/state；“视觉上有文字”不等于控件有可访问名称。
5. **走交互**：用键盘完成主任务，观察焦点移动、禁用/等待状态、错误恢复和返回路径。
6. **做视觉比较**：若有批准基线，比较截图并检查差异；没有基线时，人工检查溢出、遮挡、截断、错位、跳动、层级和响应式重排。

截图是证据，不是自动结论。像素差异可能来自字体、抗锯齿或动态数据；无像素差异也不能证明键盘和语义正确。把 screenshot、a11y tree、交互观察组合使用。

### 验收矩阵

| 维度 | 最小样本 | 要观察什么 |
|---|---|---|
| 视口 | 支持范围内窄屏 + 桌面 | 溢出、重排、触控/点击目标、固定层遮挡 |
| 数据 | loading / empty / error / success / partial（适用时） | 是否误导、恢复动作、旧数据是否保留 |
| 输入 | 键盘 + 指针 | Tab 顺序、焦点、hover-only 功能、手势替代 |
| 感知 | 浅/深色、放大、对比度 | 可读性、只靠颜色、文本截断 |
| 语义 | accessibility tree | name/role/state、标题与 landmark、live status |

Tauri v2 仍使用 webview，Web DOM/a11y 检查同样有价值；另需在目标操作系统检查原生窗口、系统缩放、快捷键和 webview 差异。版本相关 Tauri/React/组件库 API 用 Context7 查询，不凭记忆写属性或事件名。

## 自动检查能做什么

自动 a11y 扫描适合发现缺 label、部分错误 ARIA、部分对比度问题；组件测试适合断言用户可见行为；截图回归适合发现已批准画面的意外变化。它们互补但都不能替代真实键盘路径与视觉检查。

## 来源

- https://www.w3.org/TR/WCAG22/
- https://www.w3.org/WAI/WCAG22/Understanding/keyboard.html
- https://www.w3.org/WAI/WCAG22/Understanding/focus-visible.html
- https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html
- https://www.w3.org/WAI/WCAG22/Understanding/non-text-content.html
- https://www.w3.org/WAI/WCAG22/Understanding/labels-or-instructions.html
- https://www.w3.org/WAI/WCAG22/Understanding/error-identification.html
- https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html
- https://www.w3.org/WAI/ARIA/apg/practices/read-me-first/
- https://developer.apple.com/design/human-interface-guidelines/accessibility
