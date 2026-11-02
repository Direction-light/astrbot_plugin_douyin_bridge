"""examples/sample-report.md 必须真的能被解析。

README 让陌生人拿这份文件跑通"30 秒看到效果"，所以它自己不能是错的：
解析不出来，别人照着做就是一头雾水。顺带钉住几件事——
示例里必须是假 id，不能出现任何真实视频或作者。
"""

import shutil
from pathlib import Path

from core.report import parse_report, read_reports

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "examples" / "sample-report.md"


def _items():
    return parse_report(SAMPLE.read_text(encoding="utf-8")).items


def test_sample_report_exists():
    assert SAMPLE.is_file()


def test_sample_report_parses_into_worth_items():
    assert len(_items()) == 3


def test_sample_items_have_everything_the_prompt_needs():
    for item in _items():
        assert item.title, f"{item.aweme_id} 缺标题"
        assert item.why, f"{item.aweme_id} 缺「为什么值得」"
        assert item.url.startswith("https://"), f"{item.aweme_id} 缺链接"


def test_sample_side_section_is_excluded():
    """「顺带一提」和「没把握」都不算推荐。"""
    ids = [it.aweme_id for it in _items()]
    assert "7000000000000000004" not in ids
    assert "7000000000000000005" not in ids


def test_sample_uses_obviously_fake_ids():
    """示例里的 id 必须是 700000000000000xxxx 这种，不是真视频。"""
    for item in _items():
        assert item.aweme_id.startswith("7000000000000000"), item.aweme_id


def test_readme_walkthrough_works(tmp_path):
    """README 教的做法：把示例拷成当天的文件，插件就能读到。"""
    shutil.copy(SAMPLE, tmp_path / "2026-11-01.md")
    items = read_reports(tmp_path, ["2026-11-01"])
    assert len(items) == 3
