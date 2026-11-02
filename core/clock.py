"""静默时段 / 发送窗口判定。

规则（用户定的）：23:00–09:00 只存不发，09:00 之后统一发送。
和 douyin-eye 的 quiet.py 同一套语义：支持跨午夜区间，左闭右开。
"""

from __future__ import annotations

from datetime import datetime, timedelta

# 最多往前翻几天。配错成 99 不该一口气读一百份报告。
MAX_LOOKBACK_DAYS = 7


def parse_range(text: str) -> tuple[int, int]:
    """`"23:00-09:00"` -> (1380, 540)，单位是当天分钟数。"""
    raw = (text or "").strip()
    if not raw:
        raise ValueError("empty quiet range")
    parts = raw.split("-")
    if len(parts) != 2:
        raise ValueError(f"bad quiet range: {text!r}")

    def to_minutes(s: str) -> int:
        s = s.strip()
        hh, sep, mm = s.partition(":")
        if not sep or not hh.isdigit() or not mm.isdigit():
            raise ValueError(f"bad time: {s!r}")
        h, m = int(hh), int(mm)
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError(f"time out of range: {s!r}")
        return h * 60 + m

    start, end = to_minutes(parts[0]), to_minutes(parts[1])
    if start == end:
        raise ValueError(f"quiet range start equals end: {text!r}")
    return start, end


def in_quiet(when: datetime, text: str) -> bool:
    """是否处于静默时段。空配置 = 从不静默。"""
    if not (text or "").strip():
        return False
    start, end = parse_range(text)
    now = when.hour * 60 + when.minute
    if start < end:
        return start <= now < end
    return now >= start or now < end


def can_send(when: datetime, quiet_hours: str) -> bool:
    """现在能不能往外发消息。"""
    return not in_quiet(when, quiet_hours)


def report_days(when: datetime, lookback_days: int = 1) -> list[str]:
    """要读哪几天的报告，`YYYY-MM-DD`，**旧的在前**。

    静默期是 23:00–09:00，跨了午夜，而报告是「一天一个文件」。所以 9 点后
    那一发必须同时看昨天和今天，否则 23:00 之后判断出来的条目永远发不出去
    —— 过了 00:00 它就不叫「今天」了。

    旧的排前面，是为了让补发的昨晚内容排在今早内容之前，读起来像顺时间聊下来。
    """
    try:
        days = int(lookback_days)
    except (TypeError, ValueError):
        days = 0
    days = max(0, min(MAX_LOOKBACK_DAYS, days))
    return [f"{when - timedelta(days=k):%Y-%m-%d}" for k in range(days, -1, -1)]
