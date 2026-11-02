"""跨天合并：同一个视频在昨晚和今早两份报告里都出现时，只能发一次。

报告是「一天一个文件」，跨午夜补发时同一条视频很容易在两份里都躺着，
所以合并必须按 aweme_id 去重，且**保留最早那次**（旧报告在前，先到先得）。
"""

from core.report import merge_reports, parse_report

YESTERDAY = """# 刷抖音 · 2026-11-01（第 3 轮 22:14）

> ⏰ 本轮时间：2026-11-01 22:14（北京时间）

## 值得看

### 1000000000000001
**昨夜那条** · @甲 · 20 秒
🔗 https://www.douyin.com/video/1000000000000001
**为什么值得**：昨天写的理由
**一句话**：昨天的一句话

### 1000000000000002
**只有昨晚有** · @乙 · 12 秒
🔗 https://www.douyin.com/video/1000000000000002
**为什么值得**：乙的理由
"""

TODAY = """# 刷抖音 · 2026-11-02（第 1 轮 00:30）

> ⏰ 本轮时间：2026-11-02 00:30（北京时间）

## 值得看

### 1000000000000001
**同一条又被推荐了一次** · @甲 · 20 秒
🔗 https://www.douyin.com/video/1000000000000001
**为什么值得**：今天写的理由

### 1000000000000003
**今早的** · @丙 · 30 秒
🔗 https://www.douyin.com/video/1000000000000003
**为什么值得**：丙的理由
"""


def test_same_video_appears_once_across_days():
    merged = merge_reports([parse_report(YESTERDAY), parse_report(TODAY)])
    ids = [it.aweme_id for it in merged]
    assert ids.count("1000000000000001") == 1


def test_keeps_the_earliest_block_when_a_video_repeats():
    """昨晚先推过的，用昨晚那份的说法，不是今早的。"""
    merged = merge_reports([parse_report(YESTERDAY), parse_report(TODAY)])
    first = next(it for it in merged if it.aweme_id == "1000000000000001")
    assert first.why == "昨天写的理由"


def test_order_is_oldest_day_first_then_original_order():
    """昨晚的排在今早的前面，各自内部保持原序。"""
    merged = merge_reports([parse_report(YESTERDAY), parse_report(TODAY)])
    assert [it.aweme_id for it in merged] == [
        "1000000000000001",
        "1000000000000002",
        "1000000000000003",
    ]


def test_empty_reports_merge_to_nothing():
    assert merge_reports([]) == []
    assert merge_reports([parse_report(""), parse_report("")]) == []


def test_only_worth_section_is_taken():
    """「顺带一提」里列出来的不算推荐，不能混进补发。"""
    text = YESTERDAY + "\n## 顺带一提（证据不够）\n- 9999999999999999 · @丁 · 没什么意思\n"
    merged = merge_reports([parse_report(text)])
    assert "9999999999999999" not in [it.aweme_id for it in merged]
