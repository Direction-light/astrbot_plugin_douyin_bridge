"""推送历史：让模型知道"我前几天已经跟这个人聊过什么"。

为什么需要：每次 text_chat 都是全新的 payload，模型手里没有上下文。
不定这个，今天和昨天推的内容措辞会一个模子，像复读机。

注意它和 sent.json 的分工：
- sent.json  管"同一条视频别发两遍"（按 aweme_id）
- history    管"话别说得一模一样"（记模型原话）
"""

from datetime import datetime, timedelta

from core.history import PushHistory


def _now():
    return datetime(2026, 11, 2, 9, 1)


def test_empty_history_has_nothing_to_show(tmp_path):
    h = PushHistory(tmp_path / "history.json")
    assert h.recent(_now()) == []


def test_records_and_reads_back(tmp_path):
    h = PushHistory(tmp_path / "history.json")
    h.add("老婆婆，那条讲记忆的挺有意思", ["7000000000000000001"], _now())
    recent = h.recent(_now())
    assert len(recent) == 1
    assert recent[0]["text"] == "老婆婆，那条讲记忆的挺有意思"
    assert recent[0]["ids"] == ["7000000000000000001"]


def test_old_entries_expire(tmp_path):
    """超过保留天数的就不该再喂给模型了。"""
    h = PushHistory(tmp_path / "history.json", keep_days=14)
    h.add("很久以前说过的话", [], _now() - timedelta(days=20))
    h.add("昨天说过的话", [], _now() - timedelta(days=1))
    texts = [e["text"] for e in h.recent(_now())]
    assert texts == ["昨天说过的话"]


def test_keep_days_zero_disables_it(tmp_path):
    """keep_days=0 表示这个功能关掉，行为和以前完全一致。"""
    h = PushHistory(tmp_path / "history.json", keep_days=0)
    h.add("不该被记住", [], _now())
    assert h.recent(_now()) == []


def test_recent_returns_newest_last(tmp_path):
    """按时间正序返回，模型读起来像时间线。"""
    h = PushHistory(tmp_path / "history.json")
    h.add("最早说的", [], _now() - timedelta(days=2))
    h.add("中间说的", [], _now() - timedelta(days=1))
    h.add("最近说的", [], _now())
    assert [e["text"] for e in h.recent(_now())] == ["最早说的", "中间说的", "最近说的"]


def test_recent_is_capped(tmp_path):
    """喂给模型的条数要封顶，否则提示词会爆。"""
    h = PushHistory(tmp_path / "history.json", max_entries=3)
    for i in range(10):
        h.add(f"第{i}条", [], _now() - timedelta(hours=10 - i))
    recent = h.recent(_now())
    assert len(recent) == 3
    assert recent[-1]["text"] == "第9条"


def test_long_text_is_truncated(tmp_path):
    """单条太长要截断，免得一条就把预算吃光。"""
    h = PushHistory(tmp_path / "history.json", max_chars=10)
    h.add("一二三四五六七八九十十一十二", [], _now())
    text = h.recent(_now())[0]["text"]
    assert len(text) <= 11          # 10 字 + 省略号
    assert text.endswith("…")


def test_survives_a_corrupt_file(tmp_path):
    """文件坏了不能把主循环带崩，最差就是当成空历史。"""
    path = tmp_path / "history.json"
    path.write_text("{ 这不是 json", encoding="utf-8")
    h = PushHistory(path)
    assert h.recent(_now()) == []


def test_add_on_corrupt_file_still_writes(tmp_path):
    path = tmp_path / "history.json"
    path.write_text("坏掉了", encoding="utf-8")
    h = PushHistory(path)
    h.add("还能继续记", [], _now())
    assert [e["text"] for e in PushHistory(path).recent(_now())] == ["还能继续记"]
