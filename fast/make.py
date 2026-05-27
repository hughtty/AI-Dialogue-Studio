"""
fast/make.py — CLI 入口

用法：
  python -m fast.make story "下班路上的孤独感"      # → outputs/{slug}/story.json
  python -m fast.make script <slug>                # → story_script.md + story_formatted.json
  python -m fast.make screenshots <slug>           # → screenshots/png/*.png
  python -m fast.make audio <slug>                 # → audio/*.mp3 + lines.json
  python -m fast.make video <slug>                 # → composition/ + final.mp4
  python -m fast.make all "下班路上的孤独感"        # 全套（story/script/screenshots/audio/video）
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

from . import cards, composition, llm, script_writer, screenshot, tts

ROOT = Path(__file__).parent
OUTPUTS = ROOT / "outputs"


def _slug_dir(slug: str) -> Path:
    d = OUTPUTS / slug
    d.mkdir(parents=True, exist_ok=True)
    return d


def cmd_story(theme: str, tone: str = "留白向", ai_style: str = "陪伴感",
              characters: str = "一个在外地工作的中年人") -> str:
    print(f"[story] Kimi 生成中：{theme}")
    story = llm.generate_story(theme, tone, ai_style, characters)
    slug = story["slug"]
    d = _slug_dir(slug)
    (d / "story.json").write_text(json.dumps(story, ensure_ascii=False, indent=2), encoding="utf-8")
    cards.write_cards(story, d / "cards.html")
    print(f"[story] ✓ {d.relative_to(ROOT.parent)}/story.json")
    print(f"[story] ✓ {d.relative_to(ROOT.parent)}/cards.html")
    for name, info in story.get("characters", {}).items():
        print(f"[story]   角色「{name}」→ {info.get('voice_id')} / emotion={info.get('default_emotion')}")
    return slug


def cmd_script(slug: str) -> None:
    print(f"[script] 生成脚本和格式化 JSON：{slug}")
    script_writer.generate(slug)


def cmd_screenshots(slug: str) -> None:
    print(f"[screenshots] 生成小红书截图：{slug}")
    screenshot.batch_screenshots(slug)


def cmd_audio(slug: str) -> None:
    d = OUTPUTS / slug
    story_path = d / "story.json"
    if not story_path.exists():
        sys.exit(f"找不到 {story_path}，先跑 story")
    story = json.loads(story_path.read_text(encoding="utf-8"))

    characters = story.get("characters", {})
    if not characters:
        import yaml
        voices_file = Path(__file__).parent / "voices.yml"
        voices_map, defaults = {}, {"speed": 0.95, "vol": 1.0, "pitch": 0}
        if voices_file.exists():
            raw = yaml.safe_load(voices_file.read_text(encoding="utf-8")) or {}
            defaults = raw.pop("_defaults", {}) or {}
            defaults = {"speed": 0.95, "vol": 1.0, "pitch": 0, **defaults}
            voices_map = raw
        for slide in story.get("slides", []):
            for m in slide.get("messages", []):
                name = m.get("name", m.get("role", "unknown"))
                if name not in characters:
                    voice_id = voices_map.get(name, "female-tianmei")
                    characters[name] = {"role": m.get("role", "ai"), "voice_id": voice_id, "default_emotion": "calm"}
    else:
        defaults = {"speed": 0.95, "vol": 1.0, "pitch": 0}

    flat = []
    for slide in story.get("slides", []):
        for m in slide.get("messages", []):
            name = m.get("name", m.get("role", "unknown"))
            char_info = characters.get(name, {})
            flat.append({
                "speaker": name,
                "role": m.get("role", "ai"),
                "name": name,
                "text": m.get("text", ""),
                "voice_id": m.get("voice_id") or char_info.get("voice_id", "female-tianmei"),
                "emotion": m.get("emotion") or char_info.get("default_emotion", "calm"),
            })

    audio_dir = d / "audio"
    audio_dir.mkdir(exist_ok=True)
    lines = []
    for i, l in enumerate(flat):
        text = l["text"]
        if not text:
            continue
        fname = f"{i:02d}.mp3"
        out = audio_dir / fname
        if out.exists():
            print(f"[audio] {i:02d} 已存在，跳过 ({l['speaker']})")
            lines_json_path = audio_dir / "lines.json"
            duration_ms = None
            if lines_json_path.exists():
                cached = json.loads(lines_json_path.read_text("utf-8"))
                duration_ms = next((x["duration_ms"] for x in cached if x.get("file") == fname), None)
            if not duration_ms:
                duration_ms = tts.tts_sync(text, l["voice_id"], out, emotion=l["emotion"], **defaults)
        else:
            print(f"[audio] {i:02d} 合成：{l['speaker']} [{l['emotion']}] — {text[:24]}…")
            duration_ms = tts.tts_sync(text, l["voice_id"], out, emotion=l["emotion"], **defaults)
        lines.append({
            "i": i, "file": fname, "speaker": l["speaker"], "role": l["role"],
            "name": l["name"], "text": l["text"], "duration_ms": duration_ms,
            "voice_id": l["voice_id"], "emotion": l["emotion"],
        })

    (audio_dir / "lines.json").write_text(json.dumps(lines, ensure_ascii=False, indent=2), encoding="utf-8")
    total_s = sum(x["duration_ms"] for x in lines) / 1000
    print(f"[audio] ✓ {len(lines)} 条，总时长 {total_s:.1f}s")


def cmd_video(slug: str, quality: str = "draft") -> None:
    d = OUTPUTS / slug
    if not (d / "audio" / "lines.json").exists():
        sys.exit("缺少 audio/lines.json，先跑 audio")
    print("[video] 生成 composition…")
    comp_dir = composition.build(d)
    print(f"[video] composition: {comp_dir.relative_to(ROOT.parent)}")
    out_path = d / "final.mp4"
    cmd = ["npx", "hyperframes", "render",
           "--quality", quality,
           "--output", str(out_path)]
    print(f"[video] 渲染中（{quality}）：{' '.join(cmd)}")
    rc = subprocess.call(cmd, cwd=str(comp_dir))
    if rc != 0:
        sys.exit(f"hyperframes render 失败 rc={rc}")
    print(f"[video] ✓ {out_path.relative_to(ROOT.parent)}")


def cmd_all(theme: str, **kw) -> None:
    slug = cmd_story(theme, **kw)
    cmd_script(slug)
    cmd_screenshots(slug)
    cmd_audio(slug)
    cmd_video(slug)
    print("\n" + "=" * 50)
    print("全部完成！输出目录：")
    d = OUTPUTS / slug
    print(f"  {d.relative_to(ROOT.parent)}/")
    print(f"    story.json              # 原始数据")
    print(f"    story_script.md         # 纯文字脚本（小红书文案）")
    print(f"    story_formatted.json    # 格式化数据（网页渲染用）")
    print(f"    cards.html              # 预览页")
    print(f"    screenshots/png/*.png   # 小红书 3:4 截图（{len(list((d/'screenshots'/'png').glob('*.png'))) if (d/'screenshots'/'png').exists() else '?'} 张）")
    print(f"    audio/*.mp3             # 配音音频")
    print(f"    final.mp4               # 视频号 9:16 视频")
    print("=" * 50)


def main():
    p = argparse.ArgumentParser(prog="fast.make")
    sub = p.add_subparsers(dest="cmd", required=True)

    s_story = sub.add_parser("story")
    s_story.add_argument("theme")
    s_story.add_argument("--tone", default="留白向")
    s_story.add_argument("--ai-style", default="陪伴感")
    s_story.add_argument("--characters", default="一个在外地工作的中年人")

    sub.add_parser("script").add_argument("slug")
    sub.add_parser("screenshots").add_argument("slug")
    sub.add_parser("audio").add_argument("slug")

    s_video = sub.add_parser("video")
    s_video.add_argument("slug")
    s_video.add_argument("--quality", default="draft", choices=["draft", "standard", "high"])

    s_all = sub.add_parser("all")
    s_all.add_argument("theme")
    s_all.add_argument("--tone", default="留白向")
    s_all.add_argument("--ai-style", default="陪伴感")
    s_all.add_argument("--characters", default="一个在外地工作的中年人")

    args = p.parse_args()
    if args.cmd == "story":
        cmd_story(args.theme, tone=args.tone, ai_style=args.ai_style, characters=args.characters)
    elif args.cmd == "script":
        cmd_script(args.slug)
    elif args.cmd == "screenshots":
        cmd_screenshots(args.slug)
    elif args.cmd == "audio":
        cmd_audio(args.slug)
    elif args.cmd == "video":
        cmd_video(args.slug, quality=args.quality)
    elif args.cmd == "all":
        cmd_all(args.theme, tone=args.tone, ai_style=args.ai_style, characters=args.characters)


if __name__ == "__main__":
    main()
