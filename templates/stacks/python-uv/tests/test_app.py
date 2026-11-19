import json
from pathlib import Path

import pytest

from src.app import load_seeds


def test_load_seeds_reads_items(tmp_path: Path) -> None:
    seed_file = tmp_path / "seeds.json"
    seed_file.write_text(json.dumps([{"id": "a", "title": "A"}]), encoding="utf-8")
    assert load_seeds(seed_file) == [{"id": "a", "title": "A"}]


def test_load_seeds_rejects_non_array(tmp_path: Path) -> None:
    seed_file = tmp_path / "seeds.json"
    seed_file.write_text('{"id": "a"}', encoding="utf-8")
    with pytest.raises(TypeError):
        load_seeds(seed_file)
