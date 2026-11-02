"""把报告里的「值得看」条目交给人设模型，转成对方能看懂的一两句。

不做任何网络调用 —— provider 由调用方传进来（AstrBot 的文本模型都行，
只要是 `await provider.text_chat(prompt, session_id=...)` 就够）。
"""

from __future__ import annotations

from .report import DutyItem

PROMPT_TEMPLATE = """{persona}

你今天刷抖音看到这些，挑几条讲给对方听：

{items}

要求：
- 每条说一两句，用换行分隔；最多 {max_items} 条
- 短句、口语，像在微信聊天，别像写文章
- 不要列表、不要序号、不要小标题、不要表情符号堆砌
- 不要说"视频""刷到""我看到"这类话，就当随口一提
- 有链接就自然地把链接放进去（对方想点就点）
- 如果有「一句话」这种现成的总结，可以用来参考，但别照抄
"""

# 历史单独成段，且明确写成"已经说过" —— 它是用来避开的，不是素材。
HISTORY_TEMPLATE = """
{history}

（上面这些是你之前已经跟对方说过的。别再重复同样的说法和同样的开场，
对方会觉得你在念稿。今天的这几条要换个讲的由头。）
"""


def format_item(index: int, item: DutyItem) -> str:
    bits: list[str] = []
    if item.title:
        bits.append(f"标题：{item.title}")
    if item.author:
        bits.append(f"作者：{item.author}")
    if item.why:
        bits.append(f"为什么值得：{item.why}")
    if item.one_line:
        bits.append(f"一句话：{item.one_line}")
    if item.url:
        bits.append(f"链接：{item.url}")
    body = "\n".join(f"  {b}" for b in bits)
    return f"{index}. {body}"


def format_history(history: list[dict]) -> str:
    """`[{"at": ..., "text": ...}]` -> 每行一条，带日期。"""
    lines: list[str] = []
    for entry in history:
        text = str(entry.get("text") or "").strip()
        if not text:
            continue
        stamp = str(entry.get("at") or "")[:10]
        lines.append(f"- {stamp}　{text}" if stamp else f"- {text}")
    if not lines:
        return ""
    return "你之前已经跟对方说过这些：\n" + "\n".join(lines)


def build_prompt(
    items: list[DutyItem],
    persona: str,
    max_items: int = 3,
    history: list[dict] | None = None,
) -> str:
    body = "\n\n".join(format_item(i + 1, it) for i, it in enumerate(items[:max_items]))
    prompt = PROMPT_TEMPLATE.format(
        persona=(persona or "").strip(),
        items=body,
        max_items=max_items,
    )
    seen = format_history(history or [])
    if not seen:
        return prompt
    return prompt + HISTORY_TEMPLATE.format(history=seen)


def split_messages(text: str, max_msgs: int = 3) -> list[str]:
    """模型输出按行切成若干条消息，丢空行，截断。"""
    out: list[str] = []
    for line in (text or "").splitlines():
        s = line.strip()
        if not s:
            continue
        # 去掉模型偶尔加的 `- ` / `1. ` 前缀
        if s.startswith("- "):
            s = s[2:].strip()
        out.append(s)
        if len(out) >= max_msgs:
            break
    return [s for s in out if s]
