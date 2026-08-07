# Local Git MCP Reuse Decision

> Issue: [#11](https://github.com/114August514/lean-harness/issues/11)
> Date: 2026-08-08
> Status: Phase 1 complete

## Decision

**implement a narrow Local Git MCP layer**

## Reason

Existing providers place mutation execution inside boundaries that cannot enforce the
required repository confinement, compare-before-mutate semantics, and structured error
taxonomy through a thin adapter. The gaps are in the mutation execution path itself,
not at the interface level.

## Candidates evaluated

### mcp-server-git (official MCP Git baseline)

Source: `modelcontextprotocol/servers` → `src/git`

| Dimension | Verdict | Key evidence |
|---|---|---|
| Repository boundary | PARTIAL | `--repository` opt-in; no linked worktree awareness |
| Structured facts | NOT SATISFIED | All output is human-readable text |
| Mutation boundary | PARTIAL | Single-purpose tools but no precondition checks or after-read |
| Stale-state protection | NOT SATISFIED | No expected-state parameters on any mutation |
| Safe cleanup | NOT SATISFIED | No worktree removal or branch deletion tools |
| Error semantics | NOT SATISFIED | No error classification; raw GitPython exceptions |
| Tool surface | PARTIAL | No escape hatch, but unstructured output |
| Command safety | PARTIAL | argv execution; missing `--` separators in some paths |

### git-courer

Source: `blak0p/git-courer`

| Dimension | Verdict | Key evidence |
|---|---|---|
| Repository boundary | SATISFIED | Fixed single-repo scope; no per-call path parameter |
| Structured facts | PARTIAL | status/history typed JSON; diff is text; no detached/unborn enum; no ignored enumeration; no in-progress field |
| Mutation boundary | NOT SATISFIED | Tools bundle multiple mutations (branch CREATE+switch+stash+pop; integrate MERGE+delete+push); no read→single mutation→re-read |
| Stale-state protection | NOT SATISFIED | No expected-state parameters; `confirmed=true` is consent gate, not state comparison |
| Safe cleanup | NOT SATISFIED | Worktree removal uses `--force`; branch deletion lacks tip/reachability/retained-refs verification |
| Error semantics | PARTIAL | Few special prefixes (PUSH_REJECTED, MERGE_CONFLICT); most errors are generic stderr text |
| Tool surface | PARTIAL | Semantic tools with pagination and truncation; output mixes typed JSON with human text |
| Command safety | PARTIAL | argv execution; Add/Remove/Restore lack `--` separators |
| Harness scope | PARTIAL | Bundled LLM lifecycle, session engine, auto-backup, release wizard, TUI; cannot run Git-only |

### github-mcp-server (boundary confirmation only)

| Capability | Confirmed |
|---|---|
| Toolsets | ✅ `--toolsets` / `X-MCP-Toolsets` |
| Individual tool filtering | ✅ `--tools` / `--exclude-tools` |
| Read-only mode | ✅ `--read-only` / `X-MCP-Readonly` |
| Authentication | ✅ PAT / OAuth / GitHub App |
| Transport | ✅ Remote hosted + local stdio |

## Gap analysis

The following Git Contract requirements are not satisfied by any evaluated provider
and cannot be added through a thin adapter because they require control over the
mutation execution path:

1. **Structured read facts**: typed distinction of branch/detached/unborn HEAD,
   staged/unstaged/untracked/ignored/conflict, worktrees, refs, commit identity,
   ancestry, reachability, in-progress operation.

2. **Mutation boundary**: read before facts → check mechanical preconditions →
   execute one explicit mutation → re-read after facts. Neither provider enforces
   this pattern; git-courer actively violates it by bundling multiple mutations
   per tool call.

3. **Stale-state protection**: caller supplies expected HEAD / branch tip / index
   state; server refuses mutation when expected ≠ observed. Neither provider has
   any expected-state mechanism.

4. **Safe cleanup**: worktree removal requires loss-surface enumeration (tracked
   changes, untracked, ignored, submodules, nested repos). Branch deletion requires
   exact ref, expected tip, retained refs, and actual reachability verification.
   Neither provider implements either.

5. **Error taxonomy**: caller must distinguish conflict, in-progress, stale
   precondition, missing object, wrong object type, dirty worktree, branch checked
   out elsewhere, unknown result. Both providers collapse to generic error text.

## What is reused

Per the Git Contract and working contract's reuse-first principle, the following
mature capabilities are reused directly:

- **Git mechanics** → system Git executable
- **MCP protocol / transport / schema machinery** → official MCP SDK
- **MCP interoperability validation** → MCP Inspector
- **GitHub capability** → official `github/github-mcp-server` (default reuse, no second implementation)

## What is implemented

A narrow Local Git MCP layer that wraps the system Git executable and exposes
Git Contract semantics through structured MCP tools. This layer implements only
the confirmed semantic gaps listed above — it does not reimplement Git mechanics,
MCP protocol, or workflow orchestration.
