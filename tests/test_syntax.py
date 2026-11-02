"""开源版的代码必须能在别人更老的 Python 上编译。

AstrBot 支持 Python 3.10+，不全是 3.12。`f"{'\n'.join(...)}"` 这种写法在
3.12 之前是 SyntaxError（PEP 701 之前 f-string 表达式里不许有反斜杠），
本机跑得好好的，别人一装就炸。
"""

import io
import tokenize
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _sources():
    paths = sorted(ROOT.glob("*.py")) + sorted((ROOT / "core").glob("*.py"))
    return [(p.name, p.read_text(encoding="utf-8")) for p in paths]


def _backslashes_in_fstring_expressions(source: str) -> list[tuple[int, str]]:
    """3.12 之前 f-string 的 `{...}` 里出现反斜杠就是 SyntaxError。"""
    hits: list[tuple[int, str]] = []
    depth = 0
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type == tokenize.FSTRING_START:
            depth += 1
        elif tok.type == tokenize.FSTRING_END:
            depth -= 1
        elif depth > 0 and tok.type != tokenize.FSTRING_MIDDLE and "\\" in tok.string:
            hits.append((tok.start[0], tok.string))
    return hits


@pytest.mark.parametrize("name,source", _sources())
def test_parses_under_python_310(name, source):
    hits = _backslashes_in_fstring_expressions(source)
    if hits:
        lines = ", ".join(f"第 {line} 行 {text!r}" for line, text in hits)
        raise AssertionError(
            f"{name} 里有 f-string 表达式带反斜杠（Python 3.12 才允许）：{lines}"
        )
