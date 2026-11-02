"""推送历史：记住最近跟这个人说过什么，下次让模型别复读。

为什么需要：`text_chat` 每次都是全新的 payload，模型手里没有上下文。
不补这块，今天和昨天推的话会是一个模子。

和 `sentlog` 的分工——
- `sentlog`  按 `aweme_id` 管「同一条视频别发两遍」
- `history`  按「说过的原话」管「话别说得一模一样」

两者缺一不可：视频换了但话一样，用户照样觉得是复读机。
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

DEFAULT_KEEP_DAYS = 14
DEFAULT_MAX_ENTRIES = 5
DEFAULT_MAX_CHARS = 200


class PushHistory:
    """`{"entries": [{"at": iso, "text": str, "ids": [aweme_id]}]}`

    `keep_days <= 0` 等于关掉这个功能，`recent()` 永远返回空、`add()` 不落盘，
    行为和没接这个模块完全一致。
    """

    def __init__(
        self,
        path: str | Path,
        keep_days: int = DEFAULT_KEEP_DAYS,
        max_entries: int = DEFAULT_MAX_ENTRIES,
        max_chars: int = DEFAULT_MAX_CHARS,
    ) -> None:
        self.path = Path(path)
        self.keep_days = keep_days
        self.max_entries = max(0, max_entries)
        self.max_chars = max(0, max_chars)

    # ---------------- 读写 ----------------

    def _load(self) -> list[dict]:
        """文件坏了就当空历史 —— 最多是丢了上下文，不能把主循环带崩。"""
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError, UnicodeDecodeError):
            return []
        entries = data.get("entries") if isinstance(data, dict) else None
        if not isinstance(entries, list):
            return []
        return [e for e in entries if isinstance(e, dict)]

    def _save(self, entries: list[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps({"entries": entries}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(tmp, self.path)

    # ---------------- 对外 ----------------

    def add(self, text: str, ids: list[str] | None = None, when: datetime | None = None) -> None:
        """记一条。`auto_send` 关着时调用方不该调它 —— 没发出去的话不算说过。"""
        if self.keep_days <= 0:
            return
        body = self._clip(str(text or "").strip())
        if not body:
            return
        now = when or datetime.now()
        entries = self._load()
        entries.append(
            {
                "at": now.isoformat(timespec="seconds"),
                "text": body,
                "ids": [str(i) for i in (ids or [])],
            }
        )
        self._save(self._trim(entries, now))

    def recent(self, when: datetime | None = None) -> list[dict]:
        """最近几条，**按时间正序**返回（旧的在前，读起来像时间线）。"""
        if self.keep_days <= 0:
            return []
        now = when or datetime.now()
        entries = self._trim(self._load(), now)
        if self.max_entries <= 0:
            return []
        return entries[-self.max_entries :]

    # ---------------- 内部 ----------------

    def _clip(self, text: str) -> str:
        if self.max_chars <= 0 or len(text) <= self.max_chars:
            return text
        return text[: self.max_chars] + "…"

    def _trim(self, entries: list[dict], now: datetime) -> list[dict]:
        """丢掉过期的和没有时间戳的，顺手按时间排序。"""
        cutoff = now - timedelta(days=max(self.keep_days, 1))
        kept: list[tuple[datetime, dict]] = []
        for entry in entries:
            try:
                at = datetime.fromisoformat(str(entry.get("at") or ""))
            except (TypeError, ValueError):
                continue
            if at >= cutoff:
                kept.append((at, entry))
        kept.sort(key=lambda pair: pair[0])
        return [entry for _, entry in kept]
