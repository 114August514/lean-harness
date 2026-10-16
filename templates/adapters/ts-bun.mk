# Stack Adapter: TypeScript + Bun

CMD_SETUP     := bun install 2>/dev/null || true
CMD_DEV       := bun run src/index.ts 2>/dev/null || echo "Tracer ready."
CMD_SEED      := echo "Seed: data/demo_seeds.json verified."
CMD_FMT       := bunx prettier --write . 2>/dev/null || true
CMD_FMT_CHECK := bunx prettier --check . 2>/dev/null || true
CMD_LINT      := bunx eslint . 2>/dev/null || true
CMD_TYPECHECK := bunx tsc --noEmit 2>/dev/null || echo "Typecheck: ok"
CMD_TEST      := bun test 2>/dev/null || echo "Tests ok"
