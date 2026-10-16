"""Tracer Bullet application entry point."""

import json
from pathlib import Path


def load_seeds() -> list[dict]:
    seed_path = Path("data/demo_seeds.json")
    if seed_path.exists():
        try:
            return json.loads(seed_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
    return []


def run_demo() -> None:
    seeds = load_seeds()
    print("=" * 55)
    print("🚀 App Tracer Bullet - Ready for Development")
    print(f"📦 Preloaded Seeds: {len(seeds)} items")
    for item in seeds[:3]:
        print(f"   - [{item.get('id', 'N/A')}] {item.get('name', 'Item')}")
    print("=" * 55)


def add(a: int, b: int) -> int:
    return a + b


if __name__ == "__main__":
    run_demo()
