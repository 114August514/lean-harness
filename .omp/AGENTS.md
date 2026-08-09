# Lean Harness 项目上下文

仓库中的现有文件是权威来源，OMP 只负责运行 Agent。

开始非简单工作前：

1. 阅读 `README.md`，了解架构和入口。
2. 阅读 `policy/index.md`，再按当前风险进入详细规则。
3. 使用 `skills/` 中与任务匹配的 Skill；`.omp/config.yml` 会直接加载这棵目录。
4. 需要检查点、交接、恢复或继续工作时，阅读 `continuity/index.md`。
5. 修改 Git 状态前阅读 `substrates/git/index.md`，并通过 Bash 调用原生 Git。

Issue、PR、Review、Checks、评论和托管合并统一使用 `.omp/mcp.json` 配置的官方 GitHub MCP。它不负责本地 Git 操作。

OMP 会话和上下文压缩只是临时上下文，不能替代 Continuity。OMP task isolation 已关闭，因为它的隐式 Git 操作不是 Harness 的标准流程；在获得真实 dogfooding 证据前，子任务优先用于调查和评审。

不要新增通用 Runtime Adapter、Provider 框架、Git wrapper、Skills 副本，也不要把 Policy、Continuity 或 Git 语义复制进 OMP 配置。
