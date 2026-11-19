#!/usr/bin/env bash
# Behavior tests for bin/doctor, bin/audit, bind-project.sh and the stack
# templates scaffolded by bin/new-project.
#
# Scaffolded stacks need uv, bun, go and cargo plus network access for their
# dependencies. Locally a missing toolchain is reported as SKIP; in CI
# (CI=true) it is a failure.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT_DIR"

export GIT_AUTHOR_NAME="Lean Harness Test" GIT_AUTHOR_EMAIL="test@example.invalid"
export GIT_COMMITTER_NAME="$GIT_AUTHOR_NAME" GIT_COMMITTER_EMAIL="$GIT_AUTHOR_EMAIL"

passes=0
fails=0
skips=0

pass() {
    echo "  [PASS] $1"
    passes=$((passes + 1))
}
fail() {
    echo "  [FAIL] $1"
    fails=$((fails + 1))
    if [ -n "${2:-}" ]; then
        tail -n 30 "$2" | sed 's/^/      /'
    fi
}
skip() {
    if [ "${CI:-}" = true ]; then
        fail "$1 (required in CI)"
    else
        echo "  [SKIP] $1"
        skips=$((skips + 1))
    fi
}
# Run a command quietly and return its exit status without tripping set -e.
status_of() {
    local log="$1"
    shift
    set +e
    "$@" >"$log" 2>&1
    local status=$?
    set -e
    return "$status"
}

work="$(mktemp -d "${TMPDIR:-/tmp}/harness-tooling-XXXXXX")"
trap 'rm -rf -- "$work"' EXIT
log="$work/last.log"

new_repo() {
    git init -q -b main "$1"
    git -C "$1" commit -q --allow-empty -m init
}

echo "[1/4] bin/doctor"
if status_of "$log" ./bin/doctor; then
    pass "doctor reports HEALTHY on this repository"
else
    fail "doctor failed on this repository" "$log"
fi

echo "[2/4] bin/audit"
repo="$work/audit"
new_repo "$repo"
mkdir "$repo/bin"
cp bin/audit "$repo/bin/audit"
git -C "$repo" add bin/audit
git -C "$repo" commit -q -m "add audit"
audit() { status_of "$log" "$repo/bin/audit" "$@"; }

if audit; then pass "clean tree passes"; else fail "clean tree failed" "$log"; fi
printf 'x\n' >"$repo/notes.md"
if audit; then pass "ordinary change passes"; else fail "ordinary change failed" "$log"; fi
mkdir -p "$repo/db/migrations"
printf 'select 1;\n' >"$repo/db/migrations/001.sql"
if audit; then
    fail "migration change passed"
elif grep -q 'db/migrations/001.sql' "$log"; then
    pass "migration change fails and names the file"
else
    fail "migration change failed without naming the file" "$log"
fi
rm -r "$repo/db"
printf 'KEY=\n' >"$repo/.env.example"
if audit; then pass ".env.example is not treated as a secret"; else fail ".env.example flagged" "$log"; fi
printf 'KEY=1\n' >"$repo/.env"
if audit; then fail ".env passed"; else pass ".env fails"; fi
rm "$repo/.env" "$repo/.env.example" "$repo/notes.md"

git -C "$repo" switch -q -c feature
mkdir "$repo/migrations"
printf 'select 1;\n' >"$repo/migrations/001.sql"
git -C "$repo" add migrations
git -C "$repo" commit -q -m "add migration"
printf 'y\n' >"$repo/later.md"
git -C "$repo" add later.md
git -C "$repo" commit -q -m "later change"
if audit; then
    fail "branch audit missed a migration committed before HEAD~1"
else
    pass "branch audit covers every commit since the merge-base"
fi
if audit no-such-ref; then status=0; else status=$?; fi
if [ "$status" -eq 2 ]; then pass "unknown base is a usage error"; else fail "unknown base exited $status" "$log"; fi

echo "[3/4] bind-project.sh"
proj="$work/bind"
new_repo "$proj"
if status_of "$log" ./bind-project.sh "$proj" --runtime all --dev; then
    if [ -f "$proj/.omp/config.yml" ] && [ -f "$proj/.omp/mcp.json" ] &&
        grep -qxF "@$ROOT_DIR/.omp/AGENTS.md" "$proj/.omp/AGENTS.md" &&
        grep -qxF "@$ROOT_DIR/.omp/AGENTS.md" "$proj/CLAUDE.md" &&
        [ "$(readlink "$proj/.claude/skills/finish-work")" = "$ROOT_DIR/skills/finish-work" ] &&
        [ ! -e "$proj/.claude/skills/_shared" ]; then
        pass "binds OMP and Claude Code by reference"
    else
        fail "binding files are incomplete"
    fi
else
    fail "bind --dev failed" "$log"
fi
before="$(cat "$proj/CLAUDE.md" "$proj/.omp/AGENTS.md")"
if status_of "$log" ./bind-project.sh "$proj" --runtime all --dev; then
    fail "second bind overwrote an existing binding"
elif [ "$(cat "$proj/CLAUDE.md" "$proj/.omp/AGENTS.md")" = "$before" ]; then
    pass "second bind refuses and leaves files untouched"
else
    fail "second bind modified files before refusing"
fi
if git describe --tags --exact-match >/dev/null 2>&1; then
    echo "  [INFO] HEAD is exactly tagged; release-mode refusal not exercised"
else
    proj="$work/bind-release"
    new_repo "$proj"
    if status_of "$log" ./bind-project.sh "$proj"; then
        fail "release mode bound an untagged checkout"
    elif [ ! -e "$proj/.omp" ]; then
        pass "release mode refuses an untagged checkout"
    else
        fail "release mode wrote files before refusing"
    fi
fi

echo "[4/4] bin/new-project stacks"
# stack | required tools | formatting break | failing test file | its content
probe_fmt() {
    case "$1" in
        python-uv) printf 'x=1\n' >>"$2/src/app.py" ;;
        ts-bun) printf 'export const probe  =  1;\n' >>"$2/src/index.ts" ;;
        go) printf 'var  probe = 1\n' >>"$2/main.go" ;;
        rust) printf 'fn  probe() {}\n' >>"$2/src/main.rs" ;;
    esac
}
probe_test() {
    case "$1" in
        python-uv) printf 'def test_probe() -> None:\n    assert False\n' >"$2/tests/test_probe.py" ;;
        ts-bun) printf 'import { expect, test } from "bun:test";\ntest("probe", () => expect(1).toBe(2));\n' >"$2/tests/probe.test.ts" ;;
        go) printf 'package main\n\nimport "testing"\n\nfunc TestProbe(t *testing.T) { t.Fatal("probe") }\n' >"$2/probe_test.go" ;;
        rust) mkdir -p "$2/tests" && printf '#[test]\nfn probe() {\n    panic!("probe");\n}\n' >"$2/tests/probe.rs" ;;
    esac
}
for stack in python-uv ts-bun go rust; do
    case "$stack" in
        python-uv) tools="uv" ;;
        ts-bun) tools="bun" ;;
        go) tools="go gofmt" ;;
        rust) tools="cargo" ;;
    esac
    missing=""
    for tool in $tools; do
        command -v "$tool" >/dev/null 2>&1 || missing="$missing $tool"
    done
    if [ -n "$missing" ]; then
        skip "$stack: missing$missing"
        continue
    fi

    dir="$work/proj-$stack"
    if ! status_of "$log" ./bin/new-project "$dir" --stack "$stack" --runtime omp; then
        fail "$stack: new-project failed" "$log"
        continue
    fi
    if status_of "$log" make -C "$dir" setup && status_of "$log" make -C "$dir" check &&
        status_of "$log" make -C "$dir" seed; then
        pass "$stack: setup, check and seed pass"
    else
        fail "$stack: scaffold gates failed" "$log"
        continue
    fi
    if status_of "$log" "$dir/bin/doctor"; then
        pass "$stack: doctor HEALTHY"
    else
        fail "$stack: doctor failed" "$log"
    fi

    # The gates must actually fail on broken code.
    probe_fmt "$stack" "$dir"
    if status_of "$log" make -C "$dir" fmt-check; then
        fail "$stack: fmt-check passed unformatted code"
    else
        pass "$stack: fmt-check rejects unformatted code"
    fi
    git -C "$dir" checkout -q -- .
    probe_test "$stack" "$dir"
    if status_of "$log" make -C "$dir" test; then
        fail "$stack: test passed a failing test"
    else
        pass "$stack: test rejects a failing test"
    fi
done

echo "-------------------------------------------------------"
echo "Tooling tests: $passes passed, $fails failed, $skips skipped."
[ "$fails" -eq 0 ]
