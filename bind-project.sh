#!/usr/bin/env bash
set -euo pipefail

REPOSITORY="114August514/lean-harness"

release_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
project_root="."
RUNTIME="omp"
FORCE=false
DEV_MODE=false

usage() {
    cat <<EOF
Usage: ./bind-project.sh [PROJECT_DIR] [OPTIONS]

Options:
  --runtime <omp|claude|all>   Target runtime to bind (default: omp)
  --dev                        Bind directly from local dev checkout (bypasses git tag check)
  --force                      Overwrite existing configuration
  -h, --help                   Show this help message
EOF
    exit 0
}

while [ $# -gt 0 ]; do
    case "$1" in
        --runtime)
            RUNTIME="$2"
            shift 2
            ;;
        --dev)
            DEV_MODE=true
            shift
            ;;
        --force)
            FORCE=true
            shift
            ;;
        -h|--help)
            usage
            ;;
        -*)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
        *)
            project_root="$(cd "$1" && pwd -P)"
            shift
            ;;
    esac
done

release_commit="$(git -C "$release_root" rev-parse --verify "HEAD^{commit}" 2>/dev/null || echo "unknown")"
release_tag="$(git -C "$release_root" describe --tags --exact-match 2>/dev/null || echo "dev-${release_commit:0:8}")"

if [ "$DEV_MODE" = false ] && [ "$release_tag" != dev-* ]; then
    if command -v gh >/dev/null 2>&1; then
        release_body="$(gh release view "$release_tag" --repo "$REPOSITORY" --json body --jq .body 2>/dev/null || true)"
        expected_commit="$(printf '%s\n' "$release_body" | sed -n 's/^Release commit: \([0-9a-f]\{40\}\)$/\1/p')"
        if [ -n "$expected_commit" ] && [ "$expected_commit" != "$release_commit" ]; then
            printf 'error: release commit mismatch for %s\n' "$release_tag" >&2
            exit 1
        fi
    fi
fi

escaped_root=$(printf '%s' "$release_root" | sed 's/\\/\\\\/g; s/"/\\"/g')

# 1. Bind OMP
bind_omp() {
    local binding_dir="$project_root/.omp"
    if [ -e "$binding_dir" ] && [ "$FORCE" = false ]; then
        printf 'warning: %s already exists; use --force to overwrite\n' "$binding_dir" >&2
        return 0
    fi
    mkdir -p "$binding_dir"
    cat >"$binding_dir/config.yml" <<EOF
skills:
  customDirectories:
    - "$escaped_root/skills"

workspace:
  additionalDirectories:
    - "$escaped_root"

memory:
  backend: off

autolearn:
  enabled: false

task:
  isolation:
    mode: none

github:
  enabled: false
EOF

    cat >"$binding_dir/AGENTS.md" <<EOF
# Project Context

Lean Harness root: \`$release_root\`.
Lean Harness release: \`$release_tag\` at \`$release_commit\`.

@$release_root/.omp/AGENTS.md

## Standard Project Commands
- \`make check\`   : Pre-commit gate (tests, linter, formatting)
- \`make test\`    : Run test suite
- \`make doctor\`  : Check engineering baseline
- \`make audit\`   : Check change diff for high-risk boundaries
EOF

    if [ -f "$release_root/.omp/mcp.json" ]; then
        cp "$release_root/.omp/mcp.json" "$binding_dir/mcp.json"
    fi
    printf 'Bound OMP runtime: %s\n' "$binding_dir"
}

# 2. Bind Claude Code
bind_claude() {
    local claude_skills_dir="$project_root/.claude/skills"
    mkdir -p "$claude_skills_dir"

    # Link skills
    for skill_path in "$release_root"/skills/*; do
        if [ -d "$skill_path" ] && [ "$(basename "$skill_path")" != "_shared" ]; then
            local skill_name="$(basename "$skill_path")"
            ln -sfn "$skill_path" "$claude_skills_dir/$skill_name"
        fi
    done

    # Generate or append to CLAUDE.md
    local claude_md="$project_root/CLAUDE.md"
    if [ ! -f "$claude_md" ] || [ "$FORCE" = true ]; then
        cat >"$claude_md" <<EOF
# Project Development Guide (Powered by Lean Harness)

## Core Engineering Rules
- **Search Before Writing**: Always search existing files and libraries first (\`git grep\`). Never duplicate logic.
- **Fail-to-Pass (TDD)**: Write a failing test first, verify failure, write minimal fix, verify pass.
- **Standard Verbs**:
  - \`make check\`  : Always run before declaring task complete.
  - \`make test\`   : Run test suite.
  - \`make doctor\` : Check repo health.
  - \`make audit\`  : Audit diff for risks.

## High-Risk Boundaries
- Migrations & Schema changes require an undo plan.
- Never hand-roll cryptography, date-time/timezones, or CSV/URL parsers.
EOF
        printf 'Created %s\n' "$claude_md"
    fi
    printf 'Bound Claude Code runtime: %s\n' "$claude_skills_dir"
}

case "$RUNTIME" in
    omp)
        bind_omp
        ;;
    claude)
        bind_claude
        ;;
    all)
        bind_omp
        bind_claude
        ;;
    *)
        printf 'error: unknown runtime %s\n' "$RUNTIME" >&2
        exit 1
        ;;
esac

printf 'Success: Bound Lean Harness (%s) to %s (runtime: %s)\n' "$release_tag" "$project_root" "$RUNTIME"
