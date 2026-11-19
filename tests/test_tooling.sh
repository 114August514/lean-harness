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

# Keep every Git call independent of user and system configuration
# (commit signing, hooks, default branch name).
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
export GIT_AUTHOR_NAME="Lean Harness Test" GIT_AUTHOR_EMAIL="test@example.invalid"
export GIT_COMMITTER_NAME="$GIT_AUTHOR_NAME" GIT_COMMITTER_EMAIL="$GIT_AUTHOR_EMAIL"

work="$(mktemp -d "${TMPDIR:-/tmp}/harness-tooling-XXXXXX")"
trap 'chmod -R u+w -- "$work" 2>/dev/null; rm -rf -- "$work"' EXIT
log="$work/last.log"
: >"$log"
status=0
passes=0
fails=0
skips=0

pass() {
    echo "  [PASS] $1"
    passes=$((passes + 1))
}
# fail WHAT: report a failure with the tail of the last command's output.
fail() {
    echo "  [FAIL] $1 (last exit status $status)"
    fails=$((fails + 1))
    tail -n 30 "$log" | sed 's/^/      /'
}
skip() {
    if [ "${CI:-}" = true ]; then
        echo "  [FAIL] $1 (required in CI)"
        fails=$((fails + 1))
    else
        echo "  [SKIP] $1"
        skips=$((skips + 1))
    fi
}
# run CMD...: run CMD with its output in $log and its exit status in $status.
run() {
    if "$@" >"$log" 2>&1; then status=0; else status=$?; fi
}
# expect STATUS ERE WHAT: the last run exited STATUS and printed a line matching ERE.
expect() {
    if [ "$status" -eq "$1" ] && grep -qE -- "$2" "$log"; then
        pass "$3"
    else
        fail "$3"
    fi
}
# expect_failure ERE WHAT: the last run failed and printed a line matching ERE.
expect_failure() {
    if [ "$status" -ne 0 ] && grep -qE -- "$1" "$log"; then
        pass "$2"
    else
        fail "$2"
    fi
}
new_repo() {
    git init -q -b main "$1"
    git -C "$1" commit -q --allow-empty -m init
}
# unbound DIR: DIR holds no binding files and no staging leftovers.
unbound() {
    local leftovers
    leftovers="$(find "$1" -maxdepth 1 -name '.lean-harness-bind.*')"
    [ ! -e "$1/.omp" ] && [ ! -e "$1/CLAUDE.md" ] && [ -z "$leftovers" ] &&
        { [ ! -d "$1/.claude/skills" ] || [ -z "$(ls -A "$1/.claude/skills")" ]; }
}

echo "[1/4] bin/doctor"
run ./bin/doctor
expect 0 'Doctor: HEALTHY' "doctor reports HEALTHY on this repository"

echo "[2/4] bin/audit"
repo="$work/audit"
new_repo "$repo"
mkdir "$repo/bin"
cp bin/audit "$repo/bin/audit"
git -C "$repo" add bin/audit
git -C "$repo" commit -q -m "add audit"

run "$repo/bin/audit"
expect 0 'No changes against the base' "clean tree passes"
printf 'x\n' >"$repo/notes.md"
run "$repo/bin/audit"
expect 0 'Audit: PASS' "ordinary change passes"
rm "$repo/notes.md"

mkdir -p "$repo/db/migrations"
printf 'select 1;\n' >"$repo/db/migrations/001.sql"
run "$repo/bin/audit"
expect 1 'db/migrations/001\.sql' "nested migration is critical and named"
rm -r "$repo/db"
mkdir -p "$repo/services/billing/contracts"
printf 'syntax = "proto3";\n' >"$repo/services/billing/contracts/billing.proto"
run "$repo/bin/audit"
expect 1 'services/billing/contracts/billing\.proto' "nested contract is critical and named"
rm -r "$repo/services"

printf 'KEY=\n' >"$repo/.env.example"
run "$repo/bin/audit"
expect 0 'Audit: PASS' ".env.example is not treated as a secret"
printf 'KEY=1\n' >"$repo/.env"
run "$repo/bin/audit"
expect 1 '^    \.env$' ".env is critical and named"
rm "$repo/.env" "$repo/.env.example"

mkdir "$repo/tests"
printf 'import pytest\n\n\n@pytest.mark.skip\ndef test_new():\n    assert True\n' >"$repo/tests/test_new.py"
run "$repo/bin/audit"
expect 0 'skipped tests added' "skip marker in an untracked test file is reported"
rm -r "$repo/tests"

mkdir "$repo/tests" "$repo/api"
printf '@pytest.mark.skip\ndef test_x():\n    assert True\n' >"$repo/tests/test_中文.py"
run "$repo/bin/audit"
expect 0 'skipped tests added' "skip marker in a non-ASCII test file name is reported"
printf 'openapi: 3.1.0\n' >"$repo/api/接口.yaml"
run "$repo/bin/audit"
expect 1 'api/接口\.yaml' "non-ASCII contract path is critical and named"
rm -r "$repo/tests" "$repo/api"

git -C "$repo" switch -q -c feature
mkdir "$repo/migrations"
printf 'select 1;\n' >"$repo/migrations/001.sql"
git -C "$repo" add migrations
git -C "$repo" commit -q -m "add migration"
printf 'y\n' >"$repo/later.md"
git -C "$repo" add later.md
git -C "$repo" commit -q -m "later change"
run "$repo/bin/audit"
expect 1 'migrations/001\.sql' "branch audit covers every commit since the merge-base"
run "$repo/bin/audit" no-such-ref
expect 2 'not a commit' "unknown base is rejected"
git -C "$repo" branch -q -m main trunk
run "$repo/bin/audit"
expect 2 'no default branch' "missing default branch is rejected instead of auditing nothing"
git -C "$repo" branch -q -m trunk main

repo="$work/audit-unrelated"
new_repo "$repo"
git -C "$repo" switch -q --orphan feature
mkdir "$repo/bin"
cp bin/audit "$repo/bin/audit"
git -C "$repo" add bin/audit
git -C "$repo" commit -q -m "unrelated history"
run "$repo/bin/audit"
expect 2 'no visible history' "unrelated history is rejected instead of auditing nothing"

echo "[3/4] bind-project.sh"
proj="$work/bind"
new_repo "$proj"
run ./bind-project.sh "$proj" --runtime all --dev
if [ "$status" -eq 0 ] && [ -f "$proj/.omp/config.yml" ] && [ -f "$proj/.omp/mcp.json" ] &&
    grep -qxF "@$ROOT_DIR/.omp/AGENTS.md" "$proj/.omp/AGENTS.md" &&
    grep -qxF "@$ROOT_DIR/.omp/AGENTS.md" "$proj/CLAUDE.md" &&
    [ "$(readlink "$proj/.claude/skills/finish-work")" = "$ROOT_DIR/skills/finish-work" ] &&
    [ ! -e "$proj/.claude/skills/_shared" ]; then
    pass "binds OMP and Claude Code by reference"
else
    fail "binds OMP and Claude Code by reference"
fi
before="$(cat "$proj/CLAUDE.md" "$proj/.omp/AGENTS.md" 2>/dev/null || true)"
run ./bind-project.sh "$proj" --runtime all --dev
if [ "$status" -eq 1 ] && [ "$(cat "$proj/CLAUDE.md" "$proj/.omp/AGENTS.md")" = "$before" ]; then
    pass "a second bind refuses and leaves the binding untouched"
else
    fail "a second bind refuses and leaves the binding untouched"
fi

proj="$work/bind-conflict"
new_repo "$proj"
printf 'x\n' >"$proj/.claude"
run ./bind-project.sh "$proj" --runtime all --dev
if [ "$status" -eq 1 ] && unbound "$proj" && grep -q 'not a directory' "$log"; then
    pass "a conflicting .claude is refused before anything is written"
else
    fail "a conflicting .claude is refused before anything is written"
fi

# Fault injection through a stand-in mv (bind-project.sh publishes every object
# with mv). After $FAKE_MV_BUDGET moves it fails, first running the shell
# snippet $FAKE_MV_BEFORE_FAIL to imitate a concurrent writer. When a
# destination ends with $FAKE_MV_TERM_AFTER it moves, then sends TERM to the
# script, and with FAKE_MV_TERM_SELF=1 also dies from TERM itself.
real_mv="$(command -v mv)"
mkdir "$work/fakemv"
cat >"$work/fakemv/mv" <<EOF
#!/bin/sh
count=\$(cat "\$FAKE_MV_STATE" 2>/dev/null || echo 0)
if [ "\$count" -ge "\${FAKE_MV_BUDGET:-1000}" ]; then
    if [ -n "\${FAKE_MV_BEFORE_FAIL:-}" ]; then sh -c "\$FAKE_MV_BEFORE_FAIL"; fi
    echo "mv: injected failure" >&2
    exit 1
fi
"$real_mv" "\$@" || exit
echo \$((count + 1)) >"\$FAKE_MV_STATE"
for last in "\$@"; do :; done
case "\$last" in
    *"\${FAKE_MV_TERM_AFTER:-/nothing}")
        kill -TERM "\$PPID"
        if [ -n "\${FAKE_MV_TERM_SELF:-}" ]; then kill -TERM \$\$; fi
        ;;
esac
EOF
chmod +x "$work/fakemv/mv"
# failing_bind NAME [VAR=VALUE...]: bind the fresh project $work/bind-NAME
# with the stand-in mv configured by VAR=VALUE.
failing_bind() {
    proj="$work/bind-$1"
    shift
    new_repo "$proj"
    rm -f "$work/mv-count"
    run env PATH="$work/fakemv:$PATH" FAKE_MV_STATE="$work/mv-count" "$@" \
        ./bind-project.sh "$proj" --runtime all --dev
}
# Moves: .omp, .claude, .claude/skills, then one per skill link, then CLAUDE.md.
failing_bind midway FAKE_MV_BUDGET=4
if [ "$status" -ne 0 ] && grep -q 'injected failure' "$log" && [ "$(cat "$work/mv-count")" = 4 ] &&
    unbound "$proj" && [ ! -e "$proj/.claude" ]; then
    pass "a bind that fails after publishing .omp and a skill link removes all of it"
else
    fail "a bind that fails after publishing .omp and a skill link removes all of it"
fi
failing_bind intruder FAKE_MV_BUDGET=1 \
    FAKE_MV_BEFORE_FAIL="printf 'theirs\n' >'$work/bind-intruder/.omp/notes.md'"
if [ "$status" -ne 0 ] && [ "$(cat "$proj/.omp/notes.md" 2>/dev/null)" = theirs ] &&
    [ "$(ls -A "$proj/.omp")" = notes.md ] && grep -q 'left in place.*/\.omp' "$log"; then
    pass "rollback keeps content another writer added and reports it"
else
    fail "rollback keeps content another writer added and reports it"
fi
failing_bind swapped FAKE_MV_BUDGET=1 FAKE_MV_BEFORE_FAIL="cd '$work/bind-swapped' &&
    '$real_mv' .omp .omp-aside && cp -R .omp-aside elsewhere && ln -s elsewhere .omp"
if [ "$status" -ne 0 ] && [ -f "$proj/elsewhere/config.yml" ] && [ -f "$proj/elsewhere/AGENTS.md" ] &&
    grep -q 'left in place.*/\.omp' "$log"; then
    pass "rollback does not follow a .omp replaced by a link to identical files"
else
    fail "rollback does not follow a .omp replaced by a link to identical files"
fi
failing_bind term-last FAKE_MV_TERM_AFTER=/CLAUDE.md
if [ "$status" -eq 143 ] && unbound "$proj" && [ ! -e "$proj/.claude" ]; then
    pass "TERM during the last publication still rolls everything back"
else
    fail "TERM during the last publication still rolls everything back"
fi
failing_bind term-both FAKE_MV_TERM_AFTER=/.omp FAKE_MV_TERM_SELF=1
if [ "$status" -eq 143 ] && unbound "$proj"; then
    pass "an interrupted mv that already moved .omp still gets rolled back"
else
    fail "an interrupted mv that already moved .omp still gets rolled back"
fi

# Release mode, against a tagged copy of this script and a stand-in for gh.
release="$work/release"
mkdir -p "$release/.omp" "$release/skills/demo" "$work/fakebin"
cp bind-project.sh "$release/"
cp .omp/AGENTS.md .omp/mcp.json "$release/.omp/"
printf -- '---\nname: demo\ndescription: demo\n---\n' >"$release/skills/demo/SKILL.md"
git -C "$release" init -q -b main
git -C "$release" add -A
git -C "$release" commit -q -m release
git -C "$release" tag v0.0.0-test
release_sha="$(git -C "$release" rev-parse HEAD)"
cat >"$work/fakebin/gh" <<'EOF'
#!/bin/sh
# Stand-in for `gh release view`: print $FAKE_RELEASE_BODY, fail when unset.
[ -n "${FAKE_RELEASE_BODY+set}" ] || exit 1
printf '%s\n' "$FAKE_RELEASE_BODY"
EOF
chmod +x "$work/fakebin/gh"
release_runs=0
# release_bind BODY: bind a fresh project from the release checkout while gh
# reports BODY as the release notes; BODY "-" makes gh fail.
release_bind() {
    release_runs=$((release_runs + 1))
    proj="$work/release-proj-$release_runs"
    new_repo "$proj"
    if [ "$1" = - ]; then
        run env PATH="$work/fakebin:$PATH" "$release/bind-project.sh" "$proj"
    else
        run env PATH="$work/fakebin:$PATH" FAKE_RELEASE_BODY="$1" "$release/bind-project.sh" "$proj"
    fi
}
# refused ERE WHAT: the last bind exited 1, wrote nothing and said ERE.
refused() {
    if [ "$status" -eq 1 ] && unbound "$proj" && grep -qE -- "$1" "$log"; then
        pass "$2"
    else
        fail "$2"
    fi
}
release_bind "Release commit: $release_sha"
if [ "$status" -eq 0 ] && grep -qF '`v0.0.0-test`' "$proj/.omp/AGENTS.md"; then
    pass "release mode binds a verified, clean release"
else
    fail "release mode binds a verified, clean release"
fi
release_bind "Release commit: $(printf '%040d' 0)"
refused 'do not record' "release mode refuses notes for another commit"
release_bind -
refused 'cannot read GitHub release' "release mode refuses when the release cannot be read"
printf 'x\n' >"$release/stray"
release_bind "Release commit: $release_sha"
refused 'modified, untracked or ignored' "release mode refuses a dirty checkout"
rm "$release/stray"
cp "$release/.git/index" "$work/index"
printf 'corrupt' >"$release/.git/index"
release_bind "Release commit: $release_sha"
refused 'cannot read the status' "release mode refuses when Git status fails"
cp "$work/index" "$release/.git/index"
git -C "$release" commit -q --allow-empty -m "after the tag"
release_bind "Release commit: $release_sha"
refused 'not at an exact release tag' "release mode refuses an untagged checkout"

echo "[4/4] bin/new-project stacks"
for stack in python-uv ts-bun go rust; do
    # src: file the format probes append to; fmt_says / parse_says: how the
    # formatter reports a formatting difference / a parse error; test_says:
    # how the runner reports the failing probe test.
    case "$stack" in
        python-uv)
            tools="uv"
            src=src/app.py
            unformatted='x=1'
            unparsable='def ('
            fmt_says='File would be reformatted'
            parse_says='invalid-syntax'
            probe_file=tests/test_probe.py
            probe=$'def test_probe() -> None:\n    assert False\n'
            test_says='FAILED tests/test_probe\.py::test_probe'
            ;;
        ts-bun)
            tools="bun"
            src=src/index.ts
            unformatted='export const probe  =  1;'
            unparsable='export const = ;'
            fmt_says='Formatter would have printed'
            parse_says='aborted due to parsing errors'
            probe_file=tests/probe.test.ts
            probe=$'import { expect, test } from "bun:test";\ntest("probe", () => expect(1).toBe(2));\n'
            test_says='\(fail\) probe'
            ;;
        go)
            tools="go gofmt"
            src=main.go
            unformatted='var  probe = 1'
            unparsable='func ('
            fmt_says='^main\.go$'
            parse_says='main\.go:[0-9]+:[0-9]+: expected'
            probe_file=probe_test.go
            probe=$'package main\n\nimport "testing"\n\nfunc TestProbe(t *testing.T) { t.Fatal("probe") }\n'
            test_says='--- FAIL: TestProbe'
            ;;
        rust)
            tools="cargo"
            src=src/main.rs
            unformatted='fn  probe() {}'
            unparsable='fn ('
            fmt_says='^Diff in .*src/main\.rs'
            parse_says='--> .*src/main\.rs:[0-9]+:[0-9]+'
            probe_file=tests/probe.rs
            probe=$'#[test]\nfn probe() {\n    panic!("probe");\n}\n'
            test_says='test probe \.\.\. FAILED'
            ;;
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
    run ./bin/new-project "$dir" --stack "$stack" --runtime omp
    if [ "$status" -ne 0 ]; then
        fail "$stack: new-project"
        continue
    fi
    run make -C "$dir" setup
    [ "$status" -ne 0 ] || run make -C "$dir" check
    [ "$status" -ne 0 ] || run make -C "$dir" demo
    if [ "$status" -ne 0 ]; then
        fail "$stack: setup, check and demo"
        continue
    fi
    pass "$stack: setup, check and demo pass"
    run "$dir/bin/doctor"
    expect 0 'Doctor: HEALTHY' "$stack: doctor HEALTHY"
    run make -C "$dir" audit BASE=no-such-ref
    expect 2 'not a commit' "$stack: make audit passes BASE to bin/audit"

    # The gates must fail on broken code, and for the intended reason.
    printf '%s\n' "$unformatted" >>"$dir/$src"
    run make -C "$dir" fmt-check
    expect_failure "$fmt_says" "$stack: fmt-check reports unformatted code"
    git -C "$dir" checkout -q -- .
    printf '%s\n' "$unparsable" >>"$dir/$src"
    run make -C "$dir" fmt-check
    expect_failure "$parse_says" "$stack: fmt-check fails when the formatter cannot parse"
    git -C "$dir" checkout -q -- .
    mkdir -p "$(dirname "$dir/$probe_file")"
    printf '%s' "$probe" >"$dir/$probe_file"
    run make -C "$dir" test
    expect_failure "$test_says" "$stack: test reports the failing test"
done

echo "-------------------------------------------------------"
echo "Tooling tests: $passes passed, $fails failed, $skips skipped."
[ "$fails" -eq 0 ]
