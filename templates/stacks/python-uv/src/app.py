"""Tracer bullet: load the demo seed data and print a summary."""

import json
import sys
from pathlib import Path

SEED_PATH = Path("data/demo_seeds.json")


def load_seeds(path: Path = SEED_PATH) -> list[dict[str, object]]:
    """Return the seed items; a missing or malformed file is an error."""
    items = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(items, list):
        raise TypeError(f"{path}: expected a JSON array")
    return items


def main(args: list[str]) -> None:
    seeds = load_seeds()
    if args == ["seed"]:
        print(f"Loaded {len(seeds)} seed items from {SEED_PATH}")
        return
    print(f"Tracer bullet ready: {len(seeds)} seed items")
    for item in seeds[:3]:
        print(f"  - [{item.get('id', '?')}] {item.get('title', '')}")


if __name__ == "__main__":
    main(sys.argv[1:])
