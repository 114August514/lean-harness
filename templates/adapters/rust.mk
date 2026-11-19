# Stack adapter: Rust + Cargo

CMD_SETUP     := cargo fetch
CMD_DEV       := cargo run
CMD_SEED      := cargo run -- seed
CMD_FMT       := cargo fmt
CMD_FMT_CHECK := cargo fmt -- --check
CMD_LINT      := cargo clippy --all-targets -- -D warnings
CMD_TYPECHECK := cargo check --all-targets
CMD_TEST      := cargo test
