"""
fast/script_writer.py — 生成纯文字故事脚本和格式化 JSON。
"""
import json
import re
from pathlib import Path


def _strip(s: str) -> str:
    return re.sub(r"<#[\d.]+#>", "", s or "").strip()


def write_script(story: dict, out_path: Path) -> None:
    """生成人类可读的纯文字故事脚本（Markdown）。"""
    lines = []
    lines.append(f"# {story.get('title', '未命名')}")
    lines.append("")
    if story.get("subtitle"):
        lines.append(f"> {story['subtitle']}")
        lines.append("")

    # 角色介绍
    characters = story.get("characters", {})
    if characters:
        lines.append("## 角色")
        lines.append("")
        for name, info in characters.items():
            role = "AI" if info.get("role") == "ai" else "人类"
            voice = info.get("voice_id", "未知")
            emotion = info.get("default_emotion", "calm")
            lines.append(f"- **{name}**（{role}）— 音色：`{voice}`，基调：{emotion}")
        lines.append("")

    # 分幕对话
    lines.append("## 剧本")
    lines.append("")
    for slide in story.get("slides", []):
        num = slide.get("num", "?")
        date = slide.get("date", "")
        lines.append(f"### 第 {num} 幕 · {date}")
        lines.append("")
        for m in slide.get("messages", []):
            name = m.get("name", m.get("role", "?"))
            text = _strip(m.get("text", ""))
            emotion = m.get("emotion", "")
            emotion_tag = f"[{emotion}]" if emotion else ""
            lines.append(f"**{name}** {emotion_tag}")
            lines.append(f"{text}")
            lines.append("")
        lines.append("---")
        lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")


def write_formatted_json(story: dict, out_path: Path) -> None:
    """生成带完整样式信息的格式化 JSON，可直接用于网页渲染。"""
    formatted = {
        "meta": {
            "title": story.get("title", ""),
            "slug": story.get("slug", ""),
            "subtitle": story.get("subtitle", ""),
            "platforms": {
                "xiaohongshu": {
                    "aspect_ratio": "3:4",
                    "recommended_size": [900, 1200],
                    "output_scale": 2,
                    "card_per_screenshot": 1,
                },
                "weixin_video": {
                    "aspect_ratio": "9:16",
                    "recommended_size": [1080, 1920],
                    "format": "mp4",
                },
            },
        },
        "characters": story.get("characters", {}),
        "slides": [],
    }

    for slide in story.get("slides", []):
        slide_fmt = {
            "num": slide.get("num"),
            "date": slide.get("date"),
            "theme": _get_slide_theme(slide.get("num", 0)),
            "messages": [],
        }
        for m in slide.get("messages", []):
            slide_fmt["messages"].append({
                "role": m.get("role"),
                "name": m.get("name"),
                "text_raw": m.get("text", ""),
                "text_clean": _strip(m.get("text", "")),
                "emotion": m.get("emotion", "calm"),
                "voice_id": _resolve_voice_id(story, m),
                "style": {
                    "bubble_bg": "#f5f4f0" if m.get("role") == "ai" else "#1a1a1a",
                    "bubble_text": "#1a1a1a" if m.get("role") == "ai" else "#f5f5f5",
                    "align": "left" if m.get("role") == "ai" else "right",
                },
            })
        formatted["slides"].append(slide_fmt)

    out_path.write_text(json.dumps(formatted, ensure_ascii=False, indent=2), encoding="utf-8")


def _get_slide_theme(num: int) -> str:
    themes = {
        1: "立局",
        2: "裂缝",
        3: "张力",
        4: "转折",
        5: "留白",
    }
    return themes.get(num, "未知")


def _resolve_voice_id(story: dict, message: dict) -> str:
    name = message.get("name", message.get("role", "unknown"))
    chars = story.get("characters", {})
    if name in chars:
        return chars[name].get("voice_id", "female-tianmei")
    return "female-tianmei"


def generate(slug: str) -> tuple[Path, Path]:
    """为指定 story 生成脚本和格式化 JSON，返回两个文件路径。"""
    root = Path(__file__).parent
    outputs = root / "outputs" / slug
    story_path = outputs / "story.json"
    if not story_path.exists():
        raise FileNotFoundError(f"找不到 {story_path}")

    story = json.loads(story_path.read_text(encoding="utf-8"))

    script_path = outputs / "story_script.md"
    write_script(story, script_path)
    print(f"[script] ✓ {script_path.relative_to(root.parent)}")

    json_path = outputs / "story_formatted.json"
    write_formatted_json(story, json_path)
    print(f"[script] ✓ {json_path.relative_to(root.parent)}")

    return script_path, json_path
