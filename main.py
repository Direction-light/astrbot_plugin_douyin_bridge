"""抖音日报桥 —— AstrBot 插件。

做一件事：把 `<报告目录>/<日期>.md` 里「值得看」段的条目，按配置的人设转述成
一两条口语消息，私聊发给指定会话。

时机：静默时段（默认 23:00–09:00）只存不发；时段一结束，把**昨晚没发完的**
和今天的一起补发 —— 所以读取窗口默认是「昨天 + 今天」两天，而不是只看今天。
那边判断出值得看、这边发不出去，跨了午夜也不能丢。

报告格式见 README。本文件只做接线，所有判断逻辑在 core/ 里，各带测试。
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime
from pathlib import Path

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, MessageChain, filter
from astrbot.api.message_components import Plain
from astrbot.api.star import Context, Star
from astrbot.core import AstrBotConfig

from .core.clock import can_send, in_quiet, report_days
from .core.compose import build_prompt, split_messages
from .core.persona import SOURCE_FALLBACK, SOURCE_PATH, SOURCE_TEXT, resolve_persona
from .core.report import read_reports
from .core.sentlog import SentLog

PLUGIN_DATA = "douyin_bridge"
DEFAULT_QUIET = "23:00-09:00"
DEFAULT_LOOKBACK = 1

_SOURCE_LABEL = {
    SOURCE_PATH: "人设文件",
    SOURCE_TEXT: "配置里的文本",
    SOURCE_FALLBACK: "中性兜底（没配到人设）",
}


def _dsh_home() -> Path:
    """报告目录的默认位置。DSH_HOME 没设就退回 ~/.dsh。"""
    env = str(os.environ.get("DSH_HOME") or "").strip()
    return Path(env) if env else Path.home() / ".dsh"


def _data_dir() -> Path:
    """插件数据目录；拿不到 AstrBot 数据路径就退回插件自己的 data/。"""
    try:
        from astrbot.core.utils.astrbot_path import get_astrbot_data_path

        base = Path(get_astrbot_data_path())
        if base.is_dir():
            return base / "plugin_data" / PLUGIN_DATA
    except Exception:  # noqa: BLE001 - 只是降级，不解释
        pass
    return Path(__file__).parent / "data"


class DouyinBridge(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.context = context
        self.config = config or {}
        self.home = _dsh_home()
        self.data_dir = _data_dir()
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            logger.exception("[douyin-bridge] 数据目录建不出来，去重会失效")
        self.sent = SentLog(self.data_dir / "sent.json")
        self._task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self._persona_cache: tuple[str, str] | None = None

    # ---------------- 生命周期 ----------------

    async def initialize(self) -> None:
        if not self.config.get("enabled", True):
            logger.info("[douyin-bridge] 未启用")
            return
        self._task = asyncio.create_task(self._loop())
        logger.info(
            "[douyin-bridge] 已启动｜报告目录=%s｜静默=%s｜回看=%s天｜目标=%s",
            self._report_dir(),
            self._quiet_hours(),
            self._lookback(),
            self._target_umo() or "（未配置，不会发送）",
        )
        if not self._target_umos():
            logger.warning(
                "[douyin-bridge] 没配 target_umo，插件不会往任何地方发。"
                "去 AstrBot 面板把这个插件配置里的「发到哪个会话」填上。"
            )

    async def terminate(self) -> None:
        if self._task is not None:
            self._task.cancel()
            self._task = None

    async def _loop(self) -> None:
        interval = max(60, int(self.config.get("poll_seconds", 600)))
        await asyncio.sleep(20)
        while True:
            try:
                await self._tick()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - 定时线程绝不能死
                logger.exception("[douyin-bridge] 轮询异常")
            await asyncio.sleep(interval)

    async def _tick(self) -> int:
        quiet = self._quiet_hours()
        if not can_send(datetime.now(), quiet):
            logger.debug("[douyin-bridge] 静默时段（%s），只存不发", quiet)
            return 0
        return await self.push_today()

    # ---------------- 配置读取 ----------------

    def _quiet_hours(self) -> str:
        return str(self.config.get("quiet_hours") or DEFAULT_QUIET)

    def _lookback(self) -> int:
        try:
            return int(self.config.get("lookback_days", DEFAULT_LOOKBACK))
        except (TypeError, ValueError):
            return DEFAULT_LOOKBACK

    def _report_dir(self) -> Path:
        raw = str(self.config.get("report_dir") or "").strip()
        if raw:
            return Path(raw).expanduser()
        return self.home / "douyin-duty" / "out"

    def _target_umos(self) -> list[str]:
        """要发给谁：主目标 + 额外目标，去空去重，保序。"""
        out: list[str] = []
        for raw in [self.config.get("target_umo")] + list(self.config.get("extra_umos") or []):
            umo = str(raw or "").strip()
            if umo and umo not in out:
                out.append(umo)
        return out

    def _target_umo(self) -> str:
        """主目标（日志/状态里显示用）。"""
        targets = self._target_umos()
        return targets[0] if targets else ""

    def _persona(self) -> tuple[str, str]:
        """`(人设正文, 来源)`。路径 → 配置文本 → 中性兜底，第一次算完就缓存。"""
        if self._persona_cache is None:
            persona, source = resolve_persona(
                str(self.config.get("persona_path") or ""),
                str(self.config.get("persona_text") or ""),
            )
            if source == SOURCE_FALLBACK:
                logger.warning(
                    "[douyin-bridge] 没配到人设：persona_path 读不到"
                    "（%r）、persona_text 也是空的，这一轮用中性兜底。",
                    self.config.get("persona_path"),
                )
            self._persona_cache = (persona, source)
        return self._persona_cache

    def _provider(self):
        pid = str(self.config.get("chat_provider_id") or "").strip()
        if pid:
            provider = self.context.get_provider_by_id(pid)
            if provider is not None:
                return provider
        try:
            return self.context.get_using_provider()
        except Exception:  # noqa: BLE001 - 老版本没有这个方法
            return None

    def _read_items(self, now: datetime) -> tuple[list[str], list]:
        """读窗口内的报告，返回 `(读到的日期列表, 合并后的条目)`。"""
        days = report_days(now, self._lookback())
        return days, read_reports(self._report_dir(), days)

    # ---------------- 核心 ----------------

    async def push_today(self) -> int:
        """把窗口内还没发过的「值得看」发出去，返回发了几条消息。"""
        async with self._lock:
            umos = self._target_umos()
            if not umos:
                logger.warning("[douyin-bridge] 没配 target_umo，跳过")
                return 0
            _, items = self._read_items(datetime.now())
            if not items:
                return 0
            pending = [it for it in items if not self.sent.has(it.key)]
            if not pending:
                return 0
            cap = max(1, int(self.config.get("max_items", 3)))
            batch = pending[:cap]
            provider = self._provider()
            if provider is None:
                logger.warning("[douyin-bridge] 找不到对话模型，跳过")
                return 0
            persona, source = self._persona()
            prompt = build_prompt(batch, persona, cap)
            try:
                resp = await provider.text_chat(prompt, session_id="douyin-bridge")
                text = getattr(resp, "completion_text", "") or ""
            except Exception:  # noqa: BLE001 - 模型挂了不能影响主流程
                logger.exception("[douyin-bridge] 模型调用失败")
                return 0
            msgs = split_messages(text, cap)
            if not msgs:
                logger.warning("[douyin-bridge] 模型没吐内容，下轮再试")
                return 0
            if not bool(self.config.get("auto_send", True)):
                logger.info(
                    "[douyin-bridge] auto_send 关着，只生成不发送（人设来源=%s）：%s",
                    _SOURCE_LABEL.get(source, source),
                    msgs,
                )
                return 0
            delivered = 0
            for umo in umos:
                for msg in msgs:
                    try:
                        await self.context.send_message(umo, MessageChain([Plain(msg)]))
                        delivered += 1
                    except Exception:  # noqa: BLE001 - 一条失败不影响别人/后面的
                        logger.exception("[douyin-bridge] 发送到 %s 失败", umo)
                        continue
                    # 消息之间稍微隔一下，像真人一条条发的
                    await asyncio.sleep(1.2)
            if delivered == 0:
                logger.warning("[douyin-bridge] 一条都没发出去，标记延后重试")
                return 0
            self.sent.mark([it.key for it in batch])
            logger.info(
                "[douyin-bridge] 已推送 %d 条消息（%d 个视频）到 %d 个会话｜人设来源=%s",
                delivered,
                len(batch),
                len(umos),
                _SOURCE_LABEL.get(source, source),
            )
            return delivered

    # ---------------- 指令 ----------------

    @filter.command("抖音日报状态")
    async def cmd_status(self, event: AstrMessageEvent):
        now = datetime.now()
        days, items = self._read_items(now)
        pending = [it for it in items if not self.sent.has(it.key)]
        quiet = self._quiet_hours()
        state = "静默中（只存不发）" if in_quiet(now, quiet) else "可以发"
        _, source = self._persona()
        # 注意：这里的换行缩进要单独算变量，不能写进 f-string 的表达式里
        # —— 反斜杠进 f-string 的 {...} 只有 Python 3.12+ 允许。
        targets = "\n      ".join(self._target_umos()) or "未配置"
        yield event.plain_result(
            f"窗口：{days[0]} ~ {days[-1]}（{len(days)} 天）\n"
            f"值得看：{len(items)} 条，其中 {len(pending)} 条没发\n"
            f"现在：{state}（静默 {quiet}）\n"
            f"报告目录：{self._report_dir()}\n"
            f"人设来源：{_SOURCE_LABEL.get(source, source)}\n"
            f"目标：{targets}"
        )

    @filter.command("抖音日报推送")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def cmd_push(self, event: AstrMessageEvent):
        sent = await self.push_today()
        yield event.plain_result(f"推了 {sent} 条消息" if sent else "没有新内容可推")
