# Stack adapter: Python + uv

CMD_SETUP     := uv sync
CMD_DEV       := uv run python -m src.app
CMD_SEED      := uv run python -m src.app seed
CMD_FMT       := uv run ruff format .
CMD_FMT_CHECK := uv run ruff format --check .
CMD_LINT      := uv run ruff check .
CMD_TYPECHECK := uv run mypy src tests
CMD_TEST      := uv run pytest
