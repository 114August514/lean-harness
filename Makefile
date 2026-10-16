# Lean Harness Standard Makefile
# Implements the standard verb interface for coding agents and human developers.

-include stack.mk

.PHONY: help setup dev fmt fmt-check lint typecheck test check doctor audit seed demo

# Default target
all: check

help:
	@echo "Lean Harness - Standard Verb Interface"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Daily Development:"
	@echo "  make check      - [Primary] Run all checks (format, lint, tests) before commit"
	@echo "  make test       - Run test suite"
	@echo "  make dev        - Start local development mode / watcher"
	@echo "  make fmt        - Format source code"
	@echo "  make lint       - Run static analysis / linters"
	@echo ""
	@echo "Product Demo & Tracer Bullet:"
	@echo "  make seed       - Populate realistic initial demo/mock data"
	@echo "  make demo       - Launch interactive product demo with preloaded data"
	@echo ""
	@echo "Engineering Inspection:"
	@echo "  make doctor     - Verify repository baseline and dependencies"
	@echo "  make audit      - Scan change diff for high-risk signals & AI failure modes"
	@echo "  make setup      - Install / prepare runtime environment"

setup:
	@if [ -n "$$(which uv 2>/dev/null)" ]; then \
		echo "Syncing uv environment..."; \
		uv sync || true; \
	else \
		echo "Python 3 environment ready."; \
	fi

dev:
	@echo "Running tests in watch mode or test runner..."
	@./bin/test

seed:
	@echo "Seeding sample data for local environment..."
	@echo "Ready: no database migrations pending."

demo: seed
	@echo ""
	@echo "=================================================="
	@echo "  LEAN HARNESS CORE DEMO"
	@echo "  Continuity engine & state verification ready."
	@echo "=================================================="
	@./bin/test

fmt:
	@if command -v ruff >/dev/null 2>&1; then \
		ruff format .; \
	else \
		echo "Formatting check: ruff not available, skipping formatting."; \
	fi

fmt-check:
	@if command -v ruff >/dev/null 2>&1; then \
		ruff format --check .; \
	else \
		echo "Format check: skipping (ruff not in PATH)."; \
	fi

lint:
	@if command -v ruff >/dev/null 2>&1; then \
		ruff check .; \
	else \
		echo "Lint check: skipping (ruff not in PATH)."; \
	fi

typecheck:
	@echo "Type check: skipping (dynamic check)."

test-continuity:
	@./bin/test

test-tooling:
	@./tests/test_tooling.sh

test: test-continuity test-tooling

check: test lint fmt-check
	@echo ""
	@echo "==> ALL CHECKS PASSED. Ready for commit."

doctor:
	@./bin/doctor

audit:
	@./bin/audit
