---
name: frontend-engineering
description: >-
  前端工程知识：组件边界、React state placement、UI states、表单、accessibility、design tokens、API contracts、Core Web Vitals 与浏览器验收。用于“做页面/组件/表单”“前端状态放哪”“检查 UI 可用性”“frontend architecture / UI engineering / a11y / web performance”；视觉风格与美术设计改用 frontend-design。
---

# 前端工程

这项 skill 说明“可用、可维护的界面应是什么样”，不替代 `implement-change`、
`verify-work`、`review-work` 等工作流程。视觉方向、字体与审美表达交给
[`frontend-design`](skill://frontend-design)；接口生产端的契约、鉴权和幂等性交给
[`backend-engineering`](skill://backend-engineering)。

## 何时使用

- 设计或重构页面、组件、表单和客户端状态；
- 补齐加载、空、错误、成功或部分成功状态；
- 接入 API、生成类型并把错误映射为用户可理解的反馈；
- 检查键盘、读屏、对比度、响应式布局或 Web 性能；
- Agent 写完 UI 后，需要获得“真实渲染结果”而不是只读源码。

不用于纯视觉探索；那是 `frontend-design`。不在这里重复需求对齐、实现、验证、评审和
收尾流程；遵循仓库 `policy/` 与相应 process skill。

## 场景路由

| 当前问题 | 读取 |
|---|---|
| 组件怎么拆；state 放 local、父组件、URL、server cache 还是 global | [组件与状态](references/components-and-state.md) |
| 页面如何覆盖 loading / empty / error / success / partial；表单怎么做 | [界面状态与表单](references/ui-states-and-forms.md) |
| 键盘、焦点、语义、ARIA、对比度、读屏最低线 | [可访问性与 UI 验收](references/accessibility-and-verification.md) |
| tokens、API 契约、生成类型、错误码、Core Web Vitals | [一致性、契约与性能](references/contracts-tokens-performance.md) |
| 错误提示、确认框、Toast、空状态和字段文案 | [交互文案](references/ux-writing.md) |
| React、Tauri v2 或组件库的版本相关 API | 先用 Context7 的 `resolve-library-id`、`query-docs` 查对应版本官方文档 |

## 先抓住这些规则

1. **组件按职责和行为边界拆，不按行数拆。** 取数/编排与可复用展示分开后，状态更容易单独呈现和验证。
2. **每份状态只有一个权威来源。** 可计算值不存；只影响一个组件就留本地；兄弟要协调才提升到最近共同父级。
3. **可分享、刷新和前进后退应保留的视图状态放 URL。** 页码、筛选、排序、选中资源 ID 通常属于导航状态。
4. **服务端数据交给 server-state cache。** 它涉及过期、并发、刷新和失效，不要复制进普通 global store。
5. **异步 UI 至少建模 `loading | empty | error | success`，需要时再加 `partial`。** 显式状态避免空白页、旧数据冒充成功和互相矛盾的布尔量。
6. **表单的前端校验改善反馈，服务端校验才是信任边界。** 提交中防重复触发；错误用文字关联到字段，并保留用户已输入内容。
7. **优先原生 HTML 语义，再用 ARIA 补足复杂组件。** ARIA role 不会自动带来键盘行为；自定义控件必须实现 APG 交互约定。
8. **样式值通过语义化 design tokens 和共享组件收敛。** 一致性来自单一机制，而不是每页手调一组近似值。
9. **前端按契约生成或共享类型，按稳定 `code` 分支。** `message` 是展示文本，不是机器协议；详细边界见 `backend-engineering`。
10. **性能先测再改。** Web 页面同时看 LCP、INP、CLS；实验室数据用于定位，真实用户数据用于判断实际体验。
11. **Agent 不能用“代码看起来对”代替看界面。** 用 OMP browser 打开真实页面，留截图、检查 accessibility tree，并走键盘和关键状态。

## 一个典型场景

“订单列表加筛选和编辑表单”时：筛选与页码进入 URL；订单查询进入 server cache；
弹窗开关和未提交字段留本地；页面分别渲染首次加载、无匹配结果、失败、成功和“旧数据仍可见但刷新失败”。
表单字段有可见 label，错误与字段关联，提交中不重复发送。接口类型来自契约，`ORDER_CONFLICT`
映射为可操作文案而不是匹配后端句子。最后在真实窄屏和桌面视口截图，检查 a11y tree、Tab 顺序、焦点和三项 Core Web Vitals。

## 自查

- [ ] 状态所有权清楚，没有重复、矛盾或可推导的 state
- [ ] loading / empty / error / success / partial 的适用状态都可触发并辨认
- [ ] 表单支持键盘、可见 label、字段级文本错误和重复提交保护
- [ ] 使用语义元素；焦点可见；信息不只靠颜色；动态状态可被辅助技术获知
- [ ] 页面只消费共享/生成的契约类型，并按错误码而非 message 分支
- [ ] 样式复用 token 与组件，没有无理由的散值或第二套模式
- [ ] 已用真实浏览器截图和 accessibility tree 检查关键视口与状态
- [ ] Web 性能结论来自测量；框架 API 已用 Context7 核实版本
