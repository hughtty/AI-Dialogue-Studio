"""
fast/xiaohongshu_cards.py — 生成小红书 3:4 比例的截图 HTML。
比例：900×1200（2x 截图为 1800×2400，适合高清发布）。
每张截图 = 一个完整的对话卡片（slide）。
"""
import html as html_module
import json
import re
from pathlib import Path

W, H = 900, 1200
PADDING = 48


def _strip(s: str) -> str:
    return re.sub(r"<#[\d.]+#>", "", s or "").strip()


def _escape(s: str) -> str:
    return html_module.escape(_strip(s))


def render_slide(story: dict, slide: dict, slide_idx: int) -> str:
    """渲染单张截图的 HTML。"""
    title = _escape(story.get("title", ""))
    subtitle = _escape(story.get("subtitle", ""))
    date = _escape(slide.get("date", ""))
    num = slide.get("num", slide_idx + 1)

    messages_html = []
    for m in slide.get("messages", []):
        role = "ai" if m.get("role") == "ai" else "user"
        name = _escape(m.get("name", ""))
        text = _escape(m.get("text", ""))
        # 把换行转成 <br>
        text = text.replace("\n", "<br>")
        messages_html.append(
            f'<div class="msg-row {role}">'
            f'<div class="msg-name">{name}</div>'
            f'<div class="msg-bubble">{text}</div></div>'
        )

    return _CARD_TEMPLATE.format(
        width=W, height=H,
        padding=PADDING,
        title=title,
        subtitle=subtitle,
        date=date,
        num=num,
        messages="\n".join(messages_html),
    )


def write_screenshots(story: dict, output_dir: Path) -> list[Path]:
    """为每个 slide 生成一个截图 HTML，返回文件列表。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for i, slide in enumerate(story.get("slides", [])):
        card_html = render_slide(story, slide, i)
        out = output_dir / f"{i+1:02d}.html"
        out.write_text(card_html, encoding="utf-8")
        paths.append(out)
    return paths


_CARD_TEMPLATE = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ background:#f5f5f5; }}
.card {{
  width: {width}px; height: {height}px;
  background: linear-gradient(180deg, #fafafa 0%, #f0f0f0 100%);
  font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Helvetica Neue', sans-serif;
  padding: {padding}px;
  display: flex; flex-direction: column;
}}
.header {{
  text-align: center; margin-bottom: 24px; flex-shrink: 0;
}}
.header-title {{
  font-size: 28px; font-weight: 600; color: #1a1a1a;
  line-height: 1.3; margin-bottom: 6px;
}}
.header-subtitle {{
  font-size: 14px; color: #999; line-height: 1.4;
}}
.phone {{
  flex: 1;
  background: #fff; border-radius: 20px;
  box-shadow: 0 4px 24px rgba(0,0,0,0.08);
  display: flex; flex-direction: column;
  overflow: hidden;
}}
.phone-header {{
  padding: 16px 20px; border-bottom: 1px solid #f0f0f0;
  display: flex; align-items: center; justify-content: space-between;
  flex-shrink: 0;
}}
.phone-app {{ font-size: 14px; font-weight: 500; color: #bbb; }}
.phone-date {{ font-size: 12px; color: #ccc; }}
.messages {{
  flex: 1; padding: 20px;
  display: flex; flex-direction: column; justify-content: flex-end;
  gap: 14px; overflow: hidden;
}}
.msg-row {{ display: flex; flex-direction: column; }}
.msg-name {{
  font-size: 11px; font-weight: 500; color: #bbb;
  margin-bottom: 3px; line-height: 1;
}}
.msg-row.ai .msg-name {{ align-self: flex-start; }}
.msg-row.user .msg-name {{ align-self: flex-end; text-align: right; }}
.msg-bubble {{
  max-width: 82%; padding: 10px 14px; border-radius: 16px;
  font-size: 15px; line-height: 1.6; word-break: break-word;
}}
.msg-row.ai .msg-bubble {{
  background: #f5f4f0; color: #1a1a1a;
  align-self: flex-start; border-bottom-left-radius: 4px;
}}
.msg-row.user .msg-bubble {{
  background: #1a1a1a; color: #f5f5f5;
  align-self: flex-end; border-bottom-right-radius: 4px;
}}
.footer {{
  text-align: center; margin-top: 16px; flex-shrink: 0;
}}
.footer-badge {{
  display: inline-block; padding: 6px 14px;
  background: #1a1a1a; color: #fff;
  font-size: 12px; font-weight: 500;
  border-radius: 20px; letter-spacing: 1px;
}}
</style>
</head>
<body>
<div class="card">
  <div class="header">
    <div class="header-title">{title}</div>
    <div class="header-subtitle">{subtitle}</div>
  </div>
  <div class="phone">
    <div class="phone-header">
      <div class="phone-app">助理</div>
      <div class="phone-date">{date}</div>
    </div>
    <div class="messages">
      {messages}
    </div>
  </div>
  <div class="footer">
    <div class="footer-badge">第 {num} 幕</div>
  </div>
</div>
</body></html>
"""
