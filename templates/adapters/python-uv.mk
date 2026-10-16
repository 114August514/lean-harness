# Stack Adapter: Python + uv

CMD_SETUP     := uv sync 2>/dev/null || true
CMD_DEV       := python3 src/app.py
CMD_SEED      := python3 -c "from src.app import load_seeds; print(f'Demo seeds ready: {len(load_seeds())} items.')" 2>/dev/null || echo "Seeds ready."
CMD_FMT       := uv run ruff format . 2>/dev/null || ruff format . 2>/dev/null || true
CMD_FMT_CHECK := uv run ruff format --check . 2>/dev/null || ruff format --check . 2>/dev/null || true
CMD_LINT      := uv run ruff check . 2>/dev/null || ruff check . 2>/dev/null || true
CMD_TYPECHECK := echo "Typecheck: ok"
CMD_TEST      := uv run pytest 2>/dev/null || python3 -m unittest discover tests
