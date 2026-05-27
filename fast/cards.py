"""
fast/cards.py — 把 story.json 渲染为静态 cards.html 预览页。
"""
import html
import re
from pathlib import Path

CARD_CSS = """
:root{--bg:#0d0d0d;--bg2:#1a1a1a;--t:#f0f0f0;--t2:#999;--t3:#666;--bd:#262626}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--t);font-family:'PingFang SC','Helvetica Neue',sans-serif;
  padding:30px 16px;display:flex;flex-direction:column;align-items:center;gap:24px;min-height:100vh}
h1{font-size:22px;font-weight:500;margin-bottom:4px}
.sub{font-size:12px;color:var(--t3);margin-bottom:8px}
.story-card{width:100%;max-width:380px;background:#fff;border-radius:14px;overflow:hidden;
  box-shadow:0 2px 24px rgba(0,0,0,.5);color:#1a1a1a}
.card-header{padding:11px 15px;border-bottom:1px solid #f0ede6;display:flex;align-items:center;
  justify-content:space-between;background:#fff}
.card-num{width:22px;height:22px;border-radius:50%;background:#f0ede6;display:flex;
  align-items:center;justify-content:center;font-size:11px;font-weight:500;color:#666}
.card-app{font-size:11px;font-weight:500;color:#aaa}
.card-date{font-size:10px;color:#bbb}
.card-body{padding:14px;display:flex;flex-direction:column;gap:9px;background:#fff}
.bubble{max-width:84%;padding:9px 13px;border-radius:14px;font-size:13.5px;line-height:1.6}
.bubble-name{font-size:10px;font-weight:500;margin-bottom:3px}
.bubble.ai{background:#f5f4f0;align-self:flex-start;border-bottom-left-radius:3px}
.bubble.ai .bubble-name{color:#aaa}
.bubble.user{background:#1a1a1a;color:#f0f0f0;align-self:flex-end;border-bottom-right-radius:3px}
.bubble.user .bubble-name{color:#888;text-align:right}
"""


def _strip(s: str) -> str:
    return re.sub(r"<#[\d.]+#>", "", s or "").strip()


def render(story: dict) -> str:
    title = html.escape(story.get("title", "未命名"))
    sub = html.escape(story.get("subtitle", ""))
    parts = [f"<!doctype html><html><head><meta charset='utf-8'><title>{title}</title>",
             f"<style>{CARD_CSS}</style></head><body>",
             f"<h1>{title}</h1>",
             f"<div class='sub'>{sub}</div>"]
    for slide in story.get("slides", []):
        parts.append("<div class='story-card'>")
        parts.append(f"<div class='card-header'>"
                     f"<div class='card-num'>{slide.get('num','')}</div>"
                     f"<div class='card-app'>助理</div>"
                     f"<div class='card-date'>{html.escape(slide.get('date',''))}</div></div>")
        parts.append("<div class='card-body'>")
        for m in slide.get("messages", []):
            role = "ai" if m.get("role") == "ai" else "user"
            name = html.escape(m.get("name", ""))
            text = html.escape(_strip(m.get("text", "")))
            parts.append(f"<div class='bubble {role}'>"
                         f"<div class='bubble-name'>{name}</div>{text}</div>")
        parts.append("</div></div>")
    parts.append("</body></html>")
    return "\n".join(parts)


def write_cards(story: dict, out_path: Path) -> None:
    out_path.write_text(render(story), encoding="utf-8")
