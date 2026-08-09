# Lean Harness 项目上下文

本文件来自 Lean Harness release。开发本仓库时，当前仓库就是 release root；外部项目必须先声明固定的 release root，再导入本文件。下面的 Harness 路径都相对于该 root。

开始非简单工作前：

1. 阅读 Harness root 中的 `README.md`，了解架构和入口。
2. 阅读 Harness root 中的 `policy/index.md`，再按当前风险进入详细规则。
3. 使用 Harness root 的 `skills/` 中与任务匹配的 Skill；消费项目通过 `.omp/config.yml` 直接加载这棵目录。
4. 需要检查点、交接、恢复或继续工作时，阅读 Harness root 中的 `continuity/index.md`。
5. 修改 Git 状态前阅读 Harness root 中的 `substrates/git/index.md`，并通过 Bash 调用目标项目的原生 Git。

Agent 发起的 Issue、PR、Review、Checks、普通评论和托管合并统一使用消费项目 `.omp/mcp.json` 配置的官方 GitHub MCP。Continuity 命令可以通过自身固定的 work-state port 读写结构化事件和最小恢复 facts；不得把该 port 当作普通 GitHub 操作入口。GitHub MCP 和 Continuity 都不负责本地 Git 操作。

OMP 会话和上下文压缩只是临时上下文，不能替代 Continuity。OMP task isolation 已关闭，因为它的隐式 Git 操作不是 Harness 的标准流程；在获得真实 dogfooding 证据前，子任务优先用于调查和评审。

不要新增通用 Runtime Adapter、Provider 框架、Git wrapper、Skills 副本，也不要把 Policy、Continuity 或 Git 语义复制进 OMP 配置。
