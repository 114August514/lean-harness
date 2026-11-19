# Project-agnostic Standard Makefile Template
# Language-specific commands are parameterized via stack.mk

-include stack.mk

.PHONY: help setup dev fmt fmt-check lint typecheck test check doctor audit seed demo

# Default target
all: check

help:
	@echo "Standard Engineering Verb Interface"
	@echo ""
	@echo "Daily Development:"
	@echo "  make check      - [Primary] Run all checks (format, lint, tests) before commit"
	@echo "  make test       - Run test suite"
	@echo "  make dev        - Run local development server / watch mode (Tracer Bullet)"
	@echo "  make fmt        - Format code"
	@echo "  make lint       - Run static analysis / linters"
	@echo ""
	@echo "Product Demo & Seeding:"
	@echo "  make seed       - Populate realistic initial mock/sample data"
	@echo "  make demo       - Launch interactive product demo with preloaded data"
	@echo ""
	@echo "Engineering Inspection:"
	@echo "  make doctor     - Run baseline project health check"
	@echo "  make audit      - Scan the branch's changes for high-risk signals (BASE=<ref> to choose the base)"
	@echo "  make setup      - Install dependencies and prepare environment"

setup:
	$(CMD_SETUP)

dev:
	$(CMD_DEV)

seed:
	@$(CMD_SEED)

demo: seed
	@echo ""
	@echo "=================================================="
	@echo "  PRODUCT DEMO LAUNCHED"
	@echo "  Open docs/spec.md to follow the 30-second Demo script."
	@echo "=================================================="
	@echo ""
	$(CMD_DEV)

fmt:
	$(CMD_FMT)

fmt-check:
	$(CMD_FMT_CHECK)

lint:
	$(CMD_LINT)

typecheck:
	$(CMD_TYPECHECK)

test:
	$(CMD_TEST)

check: test lint typecheck fmt-check
	@echo ""
	@echo "==> ALL CHECKS PASSED. Clean and ready for commit."

doctor:
	./bin/doctor

audit:
	./bin/audit $(BASE)
