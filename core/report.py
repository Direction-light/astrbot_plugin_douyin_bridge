"""日报报告解析器：把每天一份的 Markdown 报告切成结构化条目。

报告格式由上游的「值班流程」定义（本仓库不包含它），长这样：

    ## 值得看

    ### 7000000000000000001
    **标题** · @作者甲 · 20 秒 · 约 75 小时前
    🔗 https://www.douyin.com/video/7000000000000000001
    📊 赞 100 · 评 10 · 藏 20 · 转 30｜评/赞 0.10 ...
    **为什么值得**：...
    **一句话**：...

    ## 顺带一提（证据不够，没算进推荐）
    - 7000000000000000002 · @作者乙 · ...

我们只取「值得看」段里的 `### <纯数字 id>` 块 —— 按上游约定
「`### <纯数字视频ID>` 这一行是宿主数配额用的」，所以它一定存在且格式稳定。

一段报告里可能有多轮（文件按轮次追加），所以同一个 id 可能出现多次；抓取时保留
第一次出现的完整块，避免后面的「本轮没拿到候选」覆盖掉前面的有效内容。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

# `### 7000000000000000001` —— 纯数字 id 的标题行
_ITEM_HEAD_RE = re.compile(r"^###\s+(\d{6,})\s*$")
# 章节标题：`## 值得看` / `## 顺带一提（...）` / `## 没把握 / 判断不了` ...
_SECTION_RE = re.compile(r"^##\s+(.+?)\s*$")
# 轮次分隔：报告里用 `# 刷抖音 · 日期（第 N 轮 ...）` 分轮
_LOOP_RE = re.compile(r"^#\s+刷抖音")

WORTH_SECTION = "值得看"


@dataclass
class DutyItem:
    """报告里的一条「值得看」。"""

    aweme_id: str
    title: str = ""
    author: str = ""
    meta: str = ""          # 「20 秒 · 约 75 小时前」这种
    url: str = ""
    stats: str = ""         # 📊 那一行
    why: str = ""           # 「为什么值得」正文
    one_line: str = ""      # 「一句话」正文
    raw: str = ""           # 原始块，兜底用
    loop_time: str = ""     # 所在轮的「本轮时间」

    @property
    def key(self) -> str:
        return f"{self.aweme_id}@{self.loop_time or 'na'}"


@dataclass
class DutyReport:
    """一份日报告。"""

    day: str = ""
    items: list[DutyItem] = field(default_factory=list)
    rounds: list[str] = field(default_factory=list)

    @property
    def worth(self) -> list[DutyItem]:
        return self.items


def _clean(text: str) -> str:
    return (text or "").strip().strip("\u200b").strip()


def _parse_item_block(aweme_id: str, block: list[str], loop_time: str) -> DutyItem:
    item = DutyItem(aweme_id=aweme_id, raw="\n".join(block), loop_time=loop_time)
    buf_key: str | None = None
    buf: list[str] = []

    def flush() -> None:
        if buf_key is None:
            return
        body = _clean("\n".join(buf))
        if buf_key == "why":
            item.why = body
        elif buf_key == "one_line":
            item.one_line = body

    for line in block:
        s = line.strip()
        if not s:
            continue
        if s.startswith("**为什么值得**"):
            flush()
            buf_key, buf = "why", [s.split("**", 2)[-1].lstrip("：:").strip()]
            continue
        if s.startswith("**一句话**"):
            flush()
            buf_key, buf = "one_line", [s.split("**", 2)[-1].lstrip("：:").strip()]
            continue
        if s.startswith("🔗"):
            item.url = s.lstrip("🔗").strip()
            continue
        if s.startswith("📊"):
            item.stats = s.lstrip("📊").strip()
            continue
        if buf_key is not None:
            buf.append(s)
            continue
        # 第一条非特殊行：`**标题** · @作者 · 20 秒 · ...`
        if not item.title:
            for part in s.split("·"):
                p = _clean(part)
                if not p:
                    continue
                if not item.title:
                    item.title = p.strip("*").strip()
                elif not item.author and (p.startswith("@")):
                    item.author = p.lstrip("@").strip()
                else:
                    item.meta = (item.meta + " · " + p) if item.meta else p
    flush()
    return item


def parse_report(text: str, day: str = "") -> DutyReport:
    """解析一份日报告，只收「值得看」段。"""
    report = DutyReport(day=day)
    seen: set[str] = set()

    lines = (text or "").splitlines()
    section = ""
    loop_time = ""
    current_id: str | None = None
    current_block: list[str] = []

    def close_item() -> None:
        nonlocal current_id, current_block
        if current_id is not None and current_id not in seen:
            seen.add(current_id)
            report.items.append(_parse_item_block(current_id, current_block, loop_time))
        current_id, current_block = None, []

    for line in lines:
        s = line.strip()

        if _LOOP_RE.match(s):
            close_item()
            continue

        if s.startswith("> ⏰ 本轮时间："):
            loop_time = s.split("本轮时间：", 1)[-1].strip()
            report.rounds.append(loop_time)
            continue

        m_sec = _SECTION_RE.match(s)
        if m_sec and not s.startswith("###"):
            close_item()
            section = m_sec.group(1)
            continue

        m_item = _ITEM_HEAD_RE.match(s)
        if m_item:
            close_item()
            if section.startswith(WORTH_SECTION):
                current_id = m_item.group(1)
                current_block = []
            continue

        if current_id is not None:
            current_block.append(line)

    close_item()
    return report


def merge_reports(reports: Iterable[DutyReport]) -> list[DutyItem]:
    """把多天的报告按顺序拼成一条待发队列。

    报告一天一个文件，跨午夜补发时同一条视频可能在两份里都出现。这里按
    `aweme_id` 去重、**先到先得**，所以调用方要把旧的那天传在前面
    （`clock.report_days` 给的就是旧→新），保住最早那条的完整内容。
    """
    merged: list[DutyItem] = []
    seen: set[str] = set()
    for report in reports:
        for item in report.items:
            if item.aweme_id in seen:
                continue
            seen.add(item.aweme_id)
            merged.append(item)
    return merged


def read_reports(directory: str | Path, days: Iterable[str]) -> list[DutyItem]:
    """按 `days` 的顺序读这个目录下 `<day>.md`，合并成待发队列。

    缺文件、空文件、读写失败一律跳过 —— 昨天那份被清理掉不该让今天的也发不出去。
    """
    base = Path(directory)
    reports: list[DutyReport] = []
    for day in days:
        path = base / f"{day}.md"
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        reports.append(parse_report(text, day=day))
    return merge_reports(reports)
