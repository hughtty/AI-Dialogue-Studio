"""
services/xiaohongshu_cards.py — 生成截图 HTML（适配 backend Line 模型）。
按平台比例预设最佳参数，系统自动适配，无需用户逐像素调节。
"""
import html
import re
from pathlib import Path

# 比例预设：每个平台的最佳版式参数
PRESETS = {
    "xhs-3-4": {
        "width": 900, "height": 1200, "label": "小红书 3:4",
        "lines_per_page": 10,
        "font_size": 15, "line_height": 1.45,
        "bubble_py": 9, "bubble_px": 13, "gap": 7, "radius": 12,
        "pad_top": 12, "pad_bottom": 12, "pad_left": 10, "pad_right": 10,
        "inner_pad": 10,
        "name_font_size": 10, "name_opacity": 0.6,
        "header_pad_x": 14, "header_pad_y": 9,
        "app_font_size": 13, "date_font_size": 11,
        "bubble_max_width": 84,
        "ai_bg": "#f5f4f0", "user_bg": "#1a1a1a", "user_color": "#f0f0f0",
    },
    "video-9-16": {
        "width": 1080, "height": 1920, "label": "视频号 9:16",
        "lines_per_page": 16,
        "font_size": 16, "line_height": 1.45,
        "bubble_py": 10, "bubble_px": 14, "gap": 8, "radius": 13,
        "pad_top": 14, "pad_bottom": 14, "pad_left": 12, "pad_right": 12,
        "inner_pad": 12,
        "name_font_size": 10, "name_opacity": 0.6,
        "header_pad_x": 16, "header_pad_y": 10,
        "app_font_size": 14, "date_font_size": 11,
        "bubble_max_width": 84,
        "ai_bg": "#f5f4f0", "user_bg": "#1a1a1a", "user_color": "#f0f0f0",
    },
    "square-1-1": {
        "width": 900, "height": 900, "label": "正方形 1:1",
        "lines_per_page": 8,
        "font_size": 15, "line_height": 1.42,
        "bubble_py": 9, "bubble_px": 13, "gap": 7, "radius": 12,
        "pad_top": 12, "pad_bottom": 12, "pad_left": 10, "pad_right": 10,
        "inner_pad": 10,
        "name_font_size": 10, "name_opacity": 0.6,
        "header_pad_x": 14, "header_pad_y": 9,
        "app_font_size": 13, "date_font_size": 11,
        "bubble_max_width": 84,
        "ai_bg": "#f5f4f0", "user_bg": "#1a1a1a", "user_color": "#f0f0f0",
    },
    "landscape-16-9": {
        "width": 1200, "height": 675, "label": "横屏 16:9",
        "lines_per_page": 6,
        "font_size": 14, "line_height": 1.4,
        "bubble_py": 8, "bubble_px": 12, "gap": 6, "radius": 11,
        "pad_top": 10, "pad_bottom": 10, "pad_left": 10, "pad_right": 10,
        "inner_pad": 10,
        "name_font_size": 9, "name_opacity": 0.6,
        "header_pad_x": 14, "header_pad_y": 8,
        "app_font_size": 12, "date_font_size": 10,
        "bubble_max_width": 84,
        "ai_bg": "#f5f4f0", "user_bg": "#1a1a1a", "user_color": "#f0f0f0",
    },
}


def _esc(s: str) -> str:
    return html.escape(str(s) if s is not None else "")


def _strip_sound_tags(text: str) -> str:
    """去掉语气词标签，用于展示。"""
    text = re.sub(r"<#[\d.]+#>", "", text)
    text = re.sub(
        r"[\[(](?:breath|sighs|laughs|chuckles|gasps|inhales|exhales|emm|"
        r"coughs|clear-throat|groans|pant|sniffs|snorts|burps|"
        r"lip-smacking|humming|hissing|sneezes)[\])]",
        "", text, flags=re.IGNORECASE,
    )
    text = re.sub(r"  +", " ", text)
    return text.strip()


def _css(count: int, ratio_key: str = "xhs-3-4") -> str:
    """根据平台比例返回动态 CSS。"""
    p = PRESETS.get(ratio_key, PRESETS["xhs-3-4"])
    justify = "center"
    font_family = "'PingFang SC','Helvetica Neue',sans-serif"
    return f"""<style>
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{width:{p['width']}px;height:{p['height']}px;overflow:hidden}}
body{{background:#f0eeea;font-family:{font_family};display:flex;flex-direction:column;align-items:center;padding:{p['pad_top']}px {p['pad_right']}px {p['pad_bottom']}px {p['pad_left']}px}}
.phone{{width:100%;height:100%;background:#fff;border-radius:14px;box-shadow:0 2px 12px rgba(0,0,0,.06);display:flex;flex-direction:column;overflow:hidden}}
.ph-header{{padding:{p['header_pad_y']}px {p['header_pad_x']}px;border-bottom:1px solid #f0ede6;display:flex;align-items:center;justify-content:space-between;background:#fff;flex-shrink:0}}
.ph-app{{font-size:{p['app_font_size']}px;font-weight:500;color:#999}}
.ph-date{{font-size:{p['date_font_size']}px;color:#bbb}}
.messages{{flex:1;padding:{p['inner_pad']}px;display:flex;flex-direction:column;justify-content:{justify};gap:{p['gap']}px;overflow:hidden;background:#fff}}
.bubble{{max-width:{p['bubble_max_width']}%;padding:{p['bubble_py']}px {p['bubble_px']}px;border-radius:{p['radius']}px;font-size:{p['font_size']}px;line-height:{p['line_height']};word-break:break-word}}
.bubble-name{{font-size:{p['name_font_size']}px;font-weight:500;margin-bottom:1px;opacity:{p['name_opacity']}}}
.bubble.ai{{background:{p['ai_bg']};align-self:flex-start;border-bottom-left-radius:3px}}
.bubble.ai .bubble-name{{color:#999}}
.bubble.user{{background:{p['user_bg']};color:{p['user_color']};align-self:flex-end;border-bottom-right-radius:3px}}
.bubble.user .bubble-name{{color:#bbb;text-align:right}}
</style>"""


def _template_head(count: int, ratio_key: str = "xhs-3-4") -> str:
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">{_css(count, ratio_key)}</head><body>"""


_TEMPLATE_TAIL = "</body></html>"


def build_slide_html(
    lines: list,
    slide_num: int = 1,
    title: str = "",
    ratio_key: str = "xhs-3-4",
) -> str:
    """为单张 slide 生成截图 HTML 字符串。"""
    p = PRESETS.get(ratio_key, PRESETS["xhs-3-4"])
    msgs = []
    for l in lines:
        is_ai = getattr(l, "role", None) == "ai" or (isinstance(l, dict) and l.get("role") == "ai")
        speaker = getattr(l, "speaker", "") or (l.get("speaker", "") if isinstance(l, dict) else "")
        text_raw = getattr(l, "text_raw", "") or (l.get("text_raw", "") if isinstance(l, dict) else "")
        text = _strip_sound_tags(text_raw)
        cls = "ai" if is_ai else "user"
        msgs.append(
            f'<div class="bubble {cls}">'
            f'<div class="bubble-name">{_esc(speaker)}</div>'
            f'{_esc(text)}</div>'
        )

    date_str = f"第 {slide_num} 张"
    if title:
        date_str = f"{_esc(title)} · {date_str}"

    return (
        _template_head(len(msgs), ratio_key)
        + f'<div class="phone">'
        + f'<div class="ph-header">'
        + f'<div class="ph-app">对话</div>'
        + f'<div class="ph-date">{date_str}</div>'
        + f'</div>'
        + f'<div class="messages">{"".join(msgs)}</div>'
        + f'</div>'
        + _TEMPLATE_TAIL
    )


def _group_slides(lines: list, ratio_key: str = "xhs-3-4") -> list[list]:
    """按平台比例预设的每页条数分组台词。"""
    p = PRESETS.get(ratio_key, PRESETS["xhs-3-4"])
    chunk = p["lines_per_page"]
    return [lines[i:i + chunk] for i in range(0, len(lines), chunk)]


def write_slide_html(
    lines: list,
    slide_num: int,
    out_path: Path,
    title: str = "",
    ratio_key: str = "xhs-3-4",
) -> Path:
    """为单张 slide 生成 HTML 文件，返回路径。"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    html_content = build_slide_html(lines, slide_num=slide_num, title=title, ratio_key=ratio_key)
    out_path.write_text(html_content, encoding="utf-8")
    return out_path


def write_screenshots(
    lines: list,
    out_dir: Path,
    title: str = "",
    ratio_key: str = "xhs-3-4",
) -> list[Path]:
    """
    为所有台词生成截图 HTML 文件。
    根据平台比例自动决定每页条数。
    返回生成的 HTML 文件路径列表。
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    slides = _group_slides(lines, ratio_key)
    paths = []
    for i, slide_lines in enumerate(slides):
        path = out_dir / f"slide_{i + 1:02d}.html"
        html_content = build_slide_html(slide_lines, slide_num=i + 1, title=title, ratio_key=ratio_key)
        path.write_text(html_content, encoding="utf-8")
        paths.append(path)
    return paths


def get_preset(ratio_key: str) -> dict:
    """获取指定比例的预设参数。"""
    return PRESETS.get(ratio_key, PRESETS["xhs-3-4"]).copy()


def list_ratios() -> list[dict]:
    """返回所有可用比例的列表，用于前端下拉选择。"""
    return [{"key": k, "label": v["label"], "width": v["width"], "height": v["height"]} for k, v in PRESETS.items()]
