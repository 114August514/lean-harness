# 一致性机制、API 契约与性能

## Design tokens 与组件一致性

Material Design 3 把 design tokens 定义为 UI 元素的构建块，并强调设计、工具与代码使用同一组 token。它们的价值不是“变量替代数字”，而是把设计决定命名并集中管理。

### 分层命名

```css
/* primitive：原始尺度，不应在业务页面随意直接消费 */
--blue-600: #2563eb;
--space-3: 0.75rem;

/* semantic：表达用途，可随主题映射 */
--color-action-primary: var(--blue-600);
--color-text-muted: var(--gray-600);
--space-control-inline: var(--space-3);

/* component（确有复用差异时） */
--button-primary-bg: var(--color-action-primary);
```

优先使用语义 token，使深色、高对比和品牌主题能改映射而不是重写页面。常见类别包括颜色、排版、间距、尺寸、圆角、阴影、层级和 motion。不要把每个偶发值都提升为 token；重复且有设计含义的决定才进入系统。

共享组件应承载稳定交互语义和状态：按钮、字段、对话框、反馈、导航等。页面组合这些原语；不要在局部复制一套近似实现。NN/g 的一致性启发式要求用户不必猜测不同词语、情境或动作是否同义，并建议同时保持产品内部一致与平台惯例。

视觉美学、品牌气质、字体和构图选择交给 [`frontend-design`](skill://frontend-design)；这里负责让选择被一致实现。

## 消费 API 契约

生产端契约由 [`backend-engineering`](skill://backend-engineering) 负责。前端消费时遵循一个事实来源：

1. 从 OpenAPI/项目共享 schema 生成请求、响应和错误类型，或直接共享同一语言的契约类型；
2. 生成物独立目录且不手改，版本随契约一起更新；
3. API adapter 负责 transport、认证头、解包与领域错误映射；页面不散落裸 `fetch` 和 response shape；
4. 对外部输入仍做运行时边界校验；TypeScript 类型不会校验运行时 JSON；
5. 契约变化时同步迁移所有调用方，不保留第二份“看起来一样”的手写接口。

```ts
// 差：展示文案一改，逻辑失效
if (error.message.includes('already exists')) { /* ... */ }

// 好：稳定机器码决定分支，文案可本地化
switch (error.code) {
  case 'ORDER_CONFLICT': return showConflict(error.details)
  case 'FORBIDDEN': return showPermissionHelp()
  default: return showUnknownError(error.requestId)
}
```

错误 `message` 可作为兜底展示或诊断信息，但不是分支协议。不要向用户直接暴露堆栈、SQL 或内部标识；可向支持流程展示 request/correlation ID。认证过期、无权限、字段错误、冲突、限流与不可达具有不同恢复动作，按契约映射。

前端“提交中禁用”不能保证命令只执行一次；需要重试或涉及付款、创建等副作用时，幂等键和语义由后端契约定义。

## Core Web Vitals

web.dev 当前把三项 Core Web Vitals 定义为：

| 指标 | 体验面 | “良好”阈值 |
|---|---|---|
| LCP | 加载 | ≤ 2.5 s |
| INP | 交互响应 | ≤ 200 ms |
| CLS | 视觉稳定 | ≤ 0.1 |

判断页面是否达到建议目标时，看移动端与桌面端分别统计的第 75 百分位。指标会演进，因此不要把旧指标（如 FID）写死进长期规范；核对 web.dev 当前定义。

### 测量顺序

- **真实用户数据（field）**回答用户实际经历什么，受设备、网络和交互影响；
- **实验室数据（lab）**用于开发中复现、诊断和阻止回归；
- lab 不能替代 field。没有真实流量时可以从 lab 建立基线，但要清楚标注证据范围。

### 常见低成本修复方向

- LCP：优先检查服务端响应、首屏关键资源、最大内容资源的加载优先级；不要把首屏主图懒加载。
- INP：缩短长任务，减少一次交互同步执行的 JS，让必要反馈尽快绘制；先 profile 再拆分。
- CLS：为图片、视频和异步占位预留尺寸；避免在已有内容上方无预留插入元素。
- 路由/组件级代码拆分、图片尺寸与格式、列表虚拟化都应由测量和真实数据规模触发，不是每页固定仪式。

Tauri 桌面应用不一定有公开网页的 field CWV，但加载、交互与稳定性仍是有用的诊断维度。不要把搜索排名阈值当作桌面产品的唯一性能目标；结合启动时间、内存、长列表和跨 IPC 调用测量。

框架优化 API（React memoization、router prefetch、Tauri command 等）随版本变化，先用 Context7 的 `resolve-library-id`、`query-docs` 查项目版本文档，再实施。

## 检查问题

- token 是否表达用途，而非只是给任意散值换名字？
- 同一控件是否只有一套语义和状态实现？
- 类型是否来自契约；生成物是否禁止手改；运行时输入是否在边界校验？
- 错误分支是否依据 `code`，恢复动作是否与错误类别匹配？
- 性能结论是否说明 field/lab、设备/网络、样本与百分位？
- 优化是否针对实际瓶颈，优化后是否用同一测量方式比较？

## 来源

- https://m3.material.io/foundations/design-tokens/overview
- https://m3.material.io/foundations/designing/overview
- https://www.nngroup.com/articles/ten-usability-heuristics/
- https://web.dev/articles/vitals
- https://react.dev/learn/choosing-the-state-structure
- https://spec.openapis.org/oas/latest.html
