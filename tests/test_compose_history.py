"""历史怎么进提示词。

要点：别让模型把历史当素材照抄，它是用来「避开」的。
"""

from core.compose import build_prompt
from core.report import DutyItem


def _item(aweme_id="7000000000000000001", title="三分钟讲明白为什么会忘记"):
    return DutyItem(
        aweme_id=aweme_id,
        title=title,
        author="作者甲",
        why="讲清楚了记忆靠关联",
        one_line="忘了不一定是坏事",
        url=f"https://www.douyin.com/video/{aweme_id}",
    )


HISTORY = [
    {"at": "2026-11-01T21:00:00", "text": "老婆婆，昨天那条猫开门的笑死我了", "ids": []},
    {"at": "2026-11-02T09:01:00", "text": "早，昨天说的做饭那个你试了没", "ids": []},
]


def test_without_history_prompt_is_unchanged():
    """不传 history 时，提示词和以前一模一样 —— 关掉功能就是回到原样。"""
    assert "之前" not in build_prompt([_item()], "人设", 3)


def test_history_appears_in_prompt():
    prompt = build_prompt([_item()], "人设", 3, history=HISTORY)
    assert "老婆婆，昨天那条猫开门的笑死我了" in prompt
    assert "早，昨天说的做饭那个你试了没" in prompt


def test_history_is_marked_as_already_said():
    """必须说清楚这些是『已经说过的』，否则模型会当成新素材照抄。"""
    prompt = build_prompt([_item()], "人设", 3, history=HISTORY)
    assert "已经跟对方说过" in prompt
    assert "重复" in prompt


def test_history_does_not_reach_the_items_section():
    """历史要单独一段，不能混进待讲条目里被当成要讲的内容。"""
    prompt = build_prompt([_item()], "人设", 3, history=HISTORY)
    items_at = prompt.index("你今天刷抖音看到这些")
    history_at = prompt.index("老婆婆，昨天那条猫开门的笑死我了")
    assert history_at > items_at


def test_empty_history_list_changes_nothing():
    assert build_prompt([_item()], "人设", 3, history=[]) == build_prompt([_item()], "人设", 3)
