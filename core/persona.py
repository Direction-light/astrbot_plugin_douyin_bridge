"""人设从哪里来：文件路径 → 面板配置里贴的文本 → 中性兜底。

为什么要有中间那层：这个插件开源给别人用，大多数人没有现成的人设 txt，
但人人都能在 AstrBot 面板里粘一段话。而写死路径+静默降级，正是「看着正常
但语气全变了」的经典事故 —— 所以这里把"用的哪一层"返回出去，让日志和
状态指令能说清楚。
"""

from __future__ import annotations

from pathlib import Path

# 兜底人设刻意写得中性：不管什么场景，别把作者自己的称呼、关系、名号带出去。
DEFAULT_PERSONA = (
    "你说话短句，像在微信上跟熟人闲聊，不像写文章。"
    "一次说一两句，别一口气倒完。不要自称 AI 或助手。"
)

SOURCE_PATH = "path"
SOURCE_TEXT = "text"
SOURCE_FALLBACK = "fallback"


def resolve_persona(
    path: str,
    text: str,
    fallback: str = DEFAULT_PERSONA,
) -> tuple[str, str]:
    """返回 `(人设正文, 来源)`，来源是 `path` / `text` / `fallback`。

    读文件失败、文件是空的、路径是空白 —— 都算"这层没有"，继续往下走，
    绝不抛异常：插件主循环不能因为人设文件消失就停摆。
    """
    raw_path = str(path or "").strip()
    if raw_path:
        try:
            body = Path(raw_path).read_text(encoding="utf-8", errors="ignore").strip()
        except OSError:
            body = ""
        if body:
            return body, SOURCE_PATH

    raw_text = str(text or "").strip()
    if raw_text:
        return raw_text, SOURCE_TEXT

    return (fallback or "").strip(), SOURCE_FALLBACK
