"""按天读报告文件：缺天、空文件、目录不存在都不能抛 —— 主循环得活着。"""

from core.report import read_reports

ITEM = """# 刷抖音 · {day}（第 1 轮 22:14）

> ⏰ 本轮时间：{day} 22:14（北京时间）

## 值得看

### {aweme}
**{title}** · @甲 · 20 秒
🔗 https://www.douyin.com/video/{aweme}
**为什么值得**：{title} 的理由
"""


def _write(dir_path, day, aweme, title):
    (dir_path / f"{day}.md").write_text(
        ITEM.format(day=day, aweme=aweme, title=title), encoding="utf-8"
    )


def test_reads_every_day_in_the_window(tmp_path):
    _write(tmp_path, "2026-11-01", "1000000000000001", "昨夜")
    _write(tmp_path, "2026-11-02", "1000000000000002", "今早")
    items = read_reports(tmp_path, ["2026-11-01", "2026-11-02"])
    assert [it.title for it in items] == ["昨夜", "今早"]


def test_missing_day_is_skipped_not_fatal(tmp_path):
    """9 点补发时昨天的文件可能早被清掉了，只剩今天也得照发。"""
    _write(tmp_path, "2026-11-02", "1000000000000002", "今早")
    items = read_reports(tmp_path, ["2026-11-01", "2026-11-02"])
    assert [it.title for it in items] == ["今早"]


def test_missing_directory_returns_empty(tmp_path):
    items = read_reports(tmp_path / "根本不存在", ["2026-11-02"])
    assert items == []


def test_empty_file_returns_empty(tmp_path):
    (tmp_path / "2026-11-02.md").write_text("", encoding="utf-8")
    assert read_reports(tmp_path, ["2026-11-02"]) == []


def test_same_video_in_two_days_survives_once(tmp_path):
    _write(tmp_path, "2026-11-01", "1000000000000001", "昨夜")
    _write(tmp_path, "2026-11-02", "1000000000000001", "今早")
    items = read_reports(tmp_path, ["2026-11-01", "2026-11-02"])
    assert [it.title for it in items] == ["昨夜"]
