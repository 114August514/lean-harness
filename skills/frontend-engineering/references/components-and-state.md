# 组件设计与状态归属

## 场景索引

- [组件边界](#组件边界)
- [状态放置决策](#状态放置决策)
- [状态形状](#状态形状)
- [React 与 Tauri 示例](#react-与-tauri-示例)

## 组件边界

组件边界表达责任，不表达文件长度。先区分三类工作：

- **展示**：把明确的 props 渲染成 UI，发出语义明确的事件；
- **编排**：读取路由、查询和权限，选择该显示哪种状态；
- **领域交互**：编辑草稿、提交命令、处理结果。

一个组件同时取数、解释业务规则、维护复杂表单并画整页时，变化原因过多，应沿这些责任拆开。
反过来，只为减少行数而创建一层原样转发 props 的 wrapper，没有形成边界。

共享组件不是“长得差不多就抽”。当语义、交互状态和变化方向一致时复用；若两个卡片只是今天外观相似，先组合小原语，避免一个塞满 `variant` 与业务分支的万能组件。NN/g 的一致性启发式强调遵循产品与平台惯例，但它是宽泛启发式，不是组件目录规范。

每个交互组件应明确其状态集合，例如按钮的 `default / hover / focus / disabled / pending`，
选择组件的 `selected / invalid / expanded`。用受控 props 暴露需要由父级协调的状态；组件内部细节则可保持非受控。

## 状态放置决策

从最窄的正确所有者开始，而不是先选状态库：

| 问题 | 放置位置 | 例子 |
|---|---|---|
| 只影响一个组件实例？ | local state | 弹窗开关、输入中的草稿 |
| 多个相邻组件必须同步？ | 最近共同父级 | Accordion 当前展开项 |
| 刷新、分享、书签、前进后退应保留？ | URL path / query | 搜索词、页码、排序、选中 ID |
| 来自远端且会过期或被别人改变？ | server-state cache | 用户列表、订单详情 |
| 整个客户端长期共享且不是服务端副本？ | context / global store | 主题、编辑器全局偏好 |
| 能由 props 或现有 state 算出？ | 不存，渲染时计算 | `fullName`、过滤后的列表 |

React 官方建议：要协调的兄弟状态提升到最近共同父级，并把该父级作为单一事实来源；状态结构应避免矛盾、冗余、重复和不必要的深层嵌套。

### URL state

URL 是导航契约，不是所有 UI 状态的垃圾桶。使用 URL 的判据是“别人打开同一 URL 是否应看到同一视图”。

```text
好：/orders?status=pending&page=2&sort=created_desc
差：把 tooltip 是否悬停、密码输入草稿塞进 query string
```

解析时提供默认值并处理非法值；更新筛选时通常重置不再有效的页码。不要同时把相同筛选维护在 URL 和 global store，否则会产生两个事实来源。

### Server cache

远端数据具有异步、共享所有权、可能过期等特征。TanStack Query 文档把 fetching、caching、synchronizing、updating server state 作为同一问题，并列出请求去重、后台刷新和 stale 判定等职责。因此优先使用项目既有的 server-state 工具，而不是把响应复制进普通 store 再手写同步。

缓存中的实体不是编辑草稿。表单可从查询结果初始化本地草稿；保存成功后按库的契约更新/失效查询。不要在每次缓存后台刷新时无条件覆盖用户未提交的输入。

### Global state

只有跨远距离消费者、生命周期与应用一致、且无法由 URL/查询/props自然提供的客户端状态才进入全局。
引入前写下消费者和所有者；“避免 prop drilling”本身不证明业务数据应全局化，组合与局部 context 可能已足够。

## 状态形状

用互斥状态代替可组合出不可能情况的多个布尔值：

```ts
// 差：可能同时 loading、success、error
{ isLoading: boolean, isSuccess: boolean, isError: boolean }

// 好：状态空间显式
{ status: 'idle' | 'loading' | 'success' | 'error', data?: Order[], error?: AppError }
```

相关字段一起更新时可组合；可以从现有值计算的派生值不另存。这样减少同步 effect，也让页面状态能够穷举。

## React 与 Tauri 示例

- React 中，受控表单、lifting state up 只是实现上述所有权原则的例子，不是要求把所有 state 提到顶层。
- Tauri v2 的窗口、事件和 command API 属于版本相关边界；先用 Context7 的 `resolve-library-id` 与 `query-docs` 查当前版本，再决定监听器生命周期和取消订阅方式。
- 桌面壳不改变 UI 状态原则：Rust command 的结果仍是远端/异步状态；窗口尺寸、系统主题等平台状态应由明确 adapter 暴露，不要散落调用。

## 来源

- https://react.dev/learn/sharing-state-between-components
- https://react.dev/learn/choosing-the-state-structure
- https://tanstack.com/query/latest/docs/framework/react/overview
- https://www.nngroup.com/articles/ten-usability-heuristics/
