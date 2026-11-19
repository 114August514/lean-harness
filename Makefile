# Lean Harness repository checks.
# Projects scaffolded by bin/new-project get their own Makefile from
# templates/project-skeleton/.

.PHONY: all help setup fmt fmt-check lint test test-continuity test-tooling check doctor audit

all: check

help:
	@echo "Lean Harness repository targets"
	@echo ""
	@echo "  make check             lint, format check and all tests (what CI runs)"
	@echo "  make test              continuity tests and tooling tests"
	@echo "  make test-continuity   continuity tests only"
	@echo "  make lint | fmt | fmt-check"
	@echo "  make doctor            repository baseline"
	@echo "  make audit [BASE=ref]  scan the change set for high-risk signals"
	@echo "  make setup             sync the uv dev environment"

setup:
	uv sync --group dev

fmt:
	uv run ruff format .

fmt-check:
	uv run ruff format --check .

lint:
	uv run ruff check .

test-continuity:
	./bin/test -q

test-tooling:
	./tests/test_tooling.sh

test: test-continuity test-tooling

check: lint fmt-check test
	@echo "==> All checks passed."

doctor:
	./bin/doctor

audit:
	./bin/audit $(BASE)
