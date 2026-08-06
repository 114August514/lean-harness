"""可控的 fake remote：用本地 JSON 文件模拟外部写操作。

用于测试"外部操作结果未知"场景：写入成功但响应丢失，
replacement agent 必须先查询远端状态，而不是盲目重试。
"""

from __future__ import annotations

import json
from pathlib import Path


class FakeRemote:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.write_count = 0

    def write(self, key: str, value: str) -> None:
        self.write_count += 1
        data = {}
        if self.path.exists():
            data = json.loads(self.path.read_text(encoding="utf-8"))
        data[key] = value
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data), encoding="utf-8")

    def read(self, key: str) -> str | None:
        if not self.path.exists():
            return None
        return json.loads(self.path.read_text(encoding="utf-8")).get(key)
