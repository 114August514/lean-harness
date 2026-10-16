#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT_DIR"

echo "=== Running Lean Harness Tooling Test Suite ==="

PASSES=0
FAILS=0

test_pass() {
    echo "  [PASS] $1"
    PASSES=$((PASSES + 1))
}

test_fail() {
    echo "  [FAIL] $1"
    FAILS=$((FAILS + 1))
}

# 1. Test bin/doctor in Core Repo
echo "[1/4] Testing bin/doctor in core repo..."
if ./bin/doctor >/dev/null 2>&1; then
    test_pass "bin/doctor passes on core repository"
else
    test_fail "bin/doctor failed on core repository"
fi

# 2. Test bin/audit in Core Repo
echo "[2/4] Testing bin/audit in core repo..."
if ./bin/audit >/dev/null 2>&1; then
    test_pass "bin/audit runs cleanly on current diff"
else
    test_fail "bin/audit failed on current diff"
fi

# 3. Test bind-project.sh in standalone repo
echo "[3/4] Testing bind-project.sh in standalone repo..."
TMP_BIND_DIR="$(mktemp -d /tmp/harness-bind-XXXXXX)"
trap 'rm -rf "$TMP_BIND_DIR"' EXIT

git -C "$TMP_BIND_DIR" init -q -b main
if ./bind-project.sh "$TMP_BIND_DIR" --runtime all --dev >/dev/null 2>&1; then
    if [ -f "$TMP_BIND_DIR/.omp/config.yml" ] && [ -d "$TMP_BIND_DIR/.claude/skills" ]; then
        test_pass "bind-project.sh binds .omp and .claude correctly"
    else
        test_fail "bind-project.sh missing .omp or .claude files"
    fi
else
    test_fail "bind-project.sh failed in standalone repo"
fi
rm -rf "$TMP_BIND_DIR"

# 4. Test bin/new-project scaffolding for all stacks
echo "[4/4] Testing bin/new-project scaffolding & runnable skeletons..."
STACKS=("python-uv" "ts-bun" "go" "rust")

for stack in "${STACKS[@]}"; do
    TMP_PROJ_DIR="$(mktemp -d /tmp/harness-proj-${stack}-XXXXXX)"
    
    if ./bin/new-project "$TMP_PROJ_DIR" --stack "$stack" --runtime all >/dev/null 2>&1; then
        # Check standard harness files
        if [ -f "$TMP_PROJ_DIR/Makefile" ] && \
           [ -f "$TMP_PROJ_DIR/stack.mk" ] && \
           [ -f "$TMP_PROJ_DIR/.gitignore" ] && \
           [ -f "$TMP_PROJ_DIR/docs/spec.md" ] && \
           [ -f "$TMP_PROJ_DIR/docs/walkthrough.md" ] && \
           [ -f "$TMP_PROJ_DIR/data/demo_seeds.json" ] && \
           [ -x "$TMP_PROJ_DIR/bin/doctor" ]; then
            test_pass "Scaffolded structure complete for $stack"
        else
            test_fail "Scaffolded structure missing essential files for $stack"
        fi

        # Check stack-specific runnable skeleton
        case "$stack" in
            python-uv)
                if [ -f "$TMP_PROJ_DIR/pyproject.toml" ] && [ -f "$TMP_PROJ_DIR/src/app.py" ]; then
                    test_pass "Tracer skeleton files present for python-uv"
                    # Run make check inside the scaffolded project
                    if make -C "$TMP_PROJ_DIR" check >/dev/null 2>&1; then
                        test_pass "make check passes out-of-the-box for python-uv"
                    else
                        test_fail "make check failed out-of-the-box for python-uv"
                    fi
                else
                    test_fail "Tracer skeleton missing for python-uv"
                fi
                ;;
            ts-bun)
                if [ -f "$TMP_PROJ_DIR/package.json" ] && [ -f "$TMP_PROJ_DIR/src/index.ts" ]; then
                    test_pass "Tracer skeleton files present for ts-bun"
                else
                    test_fail "Tracer skeleton missing for ts-bun"
                fi
                ;;
            go)
                if [ -f "$TMP_PROJ_DIR/go.mod" ] && [ -f "$TMP_PROJ_DIR/main.go" ]; then
                    test_pass "Tracer skeleton files present for go"
                else
                    test_fail "Tracer skeleton missing for go"
                fi
                ;;
            rust)
                if [ -f "$TMP_PROJ_DIR/Cargo.toml" ] && [ -f "$TMP_PROJ_DIR/src/main.rs" ]; then
                    test_pass "Tracer skeleton files present for rust"
                else
                    test_fail "Tracer skeleton missing for rust"
                fi
                ;;
        esac

        # Verify doctor in consumer project
        if (cd "$TMP_PROJ_DIR" && ./bin/doctor >/dev/null 2>&1); then
            test_pass "bin/doctor reports HEALTHY in consumer project ($stack)"
        else
            test_fail "bin/doctor failed in consumer project ($stack)"
        fi
    else
        test_fail "bin/new-project failed for stack $stack"
    fi

    rm -rf "$TMP_PROJ_DIR"
done

echo "-------------------------------------------------------"
echo "Tooling tests complete: $PASSES passed, $FAILS failed."
if [ "$FAILS" -eq 0 ]; then
    exit 0
else
    exit 1
fi
