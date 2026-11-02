"""人设来源：路径 → 配置里贴的文本 → 中性兜底。

今天踩过的坑就是路径写死了、文件没了，插件一声不响退回一句中性人设，
QQ 那头看着一切正常。所以这里要能说清楚"这次用的是哪一层"。
"""

from core.persona import DEFAULT_PERSONA, resolve_persona


def test_reads_file_when_path_is_good(tmp_path):
    f = tmp_path / "persona.txt"
    f.write_text("我是文件里的人设\n第二行", encoding="utf-8")
    persona, source = resolve_persona(str(f), "配置里的文本不该被用到")
    assert source == "path"
    assert persona == "我是文件里的人设\n第二行"


def test_falls_back_to_text_when_path_is_missing(tmp_path):
    """用户没权限/删了文件/路径写错 —— 只要面板里粘了文本就用它，别静默降级。"""
    missing = tmp_path / "nope.txt"
    persona, source = resolve_persona(str(missing), "面板里粘的人设")
    assert source == "text"
    assert persona == "面板里粘的人设"


def test_empty_file_counts_as_missing(tmp_path):
    f = tmp_path / "empty.txt"
    f.write_text("   \n\n", encoding="utf-8")
    persona, source = resolve_persona(str(f), "退到文本")
    assert source == "text"
    assert persona == "退到文本"


def test_both_empty_uses_neutral_default():
    persona, source = resolve_persona("", "")
    assert source == "fallback"
    assert persona == DEFAULT_PERSONA


def test_path_with_only_whitespace_is_ignored(tmp_path):
    persona, source = resolve_persona("   ", "文本兜底")
    assert source == "text"
    assert persona == "文本兜底"


def test_text_is_stripped():
    persona, _ = resolve_persona("", "\n  我说话短句  \n")
    assert persona == "我说话短句"


def test_default_persona_is_a_generic_placeholder_not_a_private_persona():
    """兜底人设是一两句通用描述，不是谁的人设文件。

    私人人设文件长这样：`【你是谁】` `【说话方式】` 分节、几百字。
    兜底如果长成那样，说明有人把自己的私人人设带进了开源代码。
    """
    assert 10 <= len(DEFAULT_PERSONA) <= 120
    assert "【" not in DEFAULT_PERSONA
    assert "\n" not in DEFAULT_PERSONA
