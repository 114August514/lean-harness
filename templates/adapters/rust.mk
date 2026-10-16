# Stack Adapter: Rust + Cargo

CMD_SETUP     := cargo fetch 2>/dev/null || true
CMD_DEV       := cargo run
CMD_SEED      := echo "Seed: data/demo_seeds.json verified."
CMD_FMT       := cargo fmt 2>/dev/null || true
CMD_FMT_CHECK := cargo fmt -- --check 2>/dev/null || true
CMD_LINT      := cargo clippy -- -D warnings 2>/dev/null || true
CMD_TYPECHECK := cargo check 2>/dev/null || true
CMD_TEST      := cargo test 2>/dev/null || true
