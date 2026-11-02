"""已发送记录：保证同一条视频不会一天发两次。

存法：插件数据目录下一个 JSON（`sent.json`），结构 `{"items": {"<key>": "<iso时间>"}}`。
key 由 `report.DutyItem.key` 给出，是 `aweme_id@loop_time`，所以同一条视频在不同轮次
里被推荐两次会发两遍 —— 但那本来就是两次不同轮次，用户看到的新内容，可以接受。
真要严格按 aweme_id 去重，把 key 换成 aweme_id 就行（见 `dedup_by_id`）。
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path


class SentLog:
    def __init__(self, path: str | Path, keep_days: int = 30) -> None:
        self.path = Path(path)
        self.keep_days = keep_days

    def _load(self) -> dict[str, str]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}
        items = data.get("items") if isinstance(data, dict) else None
        return items if isinstance(items, dict) else {}

    def _save(self, items: dict[str, str]) -> None:
        cutoff = datetime.now() - timedelta(days=self.keep_days)
        trimmed: dict[str, str] = {}
        for key, stamp in items.items():
            try:
                if datetime.fromisoformat(stamp) >= cutoff:
                    trimmed[key] = stamp
            except (TypeError, ValueError):
                continue
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps({"items": trimmed}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(tmp, self.path)

    def has(self, key: str) -> bool:
        return key in self._load()

    def mark(self, keys: list[str]) -> None:
        if not keys:
            return
        items = self._load()
        now = datetime.now().isoformat(timespec="seconds")
        for key in keys:
            items[key] = now
        self._save(items)

    def pending(self, keys: list[str]) -> list[str]:
        items = self._load()
        return [k for k in keys if k not in items]
