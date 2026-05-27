"""
fast/composition.py — 把 story + audio 编译成 HyperFrames composition。
画面：竖屏 1080x1920，深色背景，居中聊天卡，气泡按音频时间逐条弹入。
支持背景音乐（BGM）。
"""
import html
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional

W, H = 1080, 1920
TAIL = 1.0  # 末尾留白秒数
ENTER_DUR = 0.25  # 单条气泡入场时长（更轻，突出打字机效果）
BGM_VOL = 0.1  # 背景音量（相对人声）


def _strip(s: str) -> str:
    """去掉 TTS 标签，用于气泡显示文本。"""
    if not s:
        return ""
    # 去掉停顿标签
    s = re.sub(r"<#[\d.]+#>", "", s)
    # 去掉语气词标签
    s = re.sub(
        r"\((?:breath|sighs|laughs|chuckles|gasps|inhales|exhales|emm|"
        r"coughs|clear-throat|groans|pant|sniffs|snorts|burps|"
        r"lip-smacking|humming|hissing|sneezes)\)",
        "", s
    )
    # 去掉多余空格
    s = re.sub(r"  +", " ", s)
    return s.strip()


def _split_to_spans(text: str) -> str:
    """把文本拆成逐字 span，用于打字机动画。"""
    chars = []
    for ch in text:
        if ch == " ":
            chars.append('<span class="c">&nbsp;</span>')
        else:
            chars.append(f'<span class="c">{html.escape(ch)}</span>')
    return "".join(chars)


def _ensure_bgm(duration: float, comp_audio_dir: Path) -> Optional[Path]:
    """确保有与视频等长的 BGM。返回 BGM 路径或 None。"""
    bgm_root = Path(__file__).parent / "bgm"
    bgm_root.mkdir(exist_ok=True)

    # 优先使用用户提供的 BGM
    bgm_src = bgm_root / "default.mp3"
    if not bgm_src.exists():
        # 尝试生成一个简单的氛围音垫
        # 用 220Hz sine + reverb 生成柔和的 drone
        try:
            subprocess.run(
                [
                    "ffmpeg", "-y", "-f", "lavfi",
                    "-i", f"sine=frequency=196:duration={max(duration, 5)}",
                    "-af", "aecho=0.6:0.5:800:0.2,aecho=0.4:0.6:1200:0.15,lowpass=f=600,volume=0.04",
                    "-ar", "32000", "-ac", "1", "-b:a", "128k",
                    str(bgm_src),
                ],
                capture_output=True, check=True,
            )
        except Exception:
            # 生成失败则跳过 BGM
            return None

    # 用 ffmpeg 把 BGM 延长/截断到目标时长
    bgm_out = comp_audio_dir / "bgm.mp3"
    try:
        # 使用 apad + shortes 来循环或延长
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(bgm_src),
                "-af", f"aloop=loop=-1:size=0,atrim=start=0:end={duration},volume={BGM_VOL}",
                "-ar", "32000", "-ac", "1", "-b:a", "128k",
                str(bgm_out),
            ],
            capture_output=True, check=True,
        )
        return bgm_out
    except Exception:
        return None


def build(story_dir: Path) -> Path:
    """story_dir 含 story.json + audio/lines.json + audio/*.mp3。
    生成 composition/ 子目录，返回 composition 路径。"""
    story = json.loads((story_dir / "story.json").read_text(encoding="utf-8"))
    lines = json.loads((story_dir / "audio" / "lines.json").read_text(encoding="utf-8"))

    comp_dir = story_dir / "composition"
    comp_audio_dir = comp_dir / "audio"
    if comp_dir.exists():
        shutil.rmtree(comp_dir)
    comp_audio_dir.mkdir(parents=True)

    # 拷贝对话音频
    for ln in lines:
        src = story_dir / "audio" / ln["file"]
        shutil.copy(src, comp_audio_dir / ln["file"])

    # 计算时间轴：每条 line 顺序拼接
    starts: list[float] = []
    t = 0.0
    for ln in lines:
        starts.append(round(t, 3))
        t += ln["duration_ms"] / 1000.0
    total = round(t + TAIL, 3)

    # 准备 BGM
    bgm_path = _ensure_bgm(total, comp_audio_dir)
    bgm_audio_html = ""
    if bgm_path:
        bgm_audio_html = (
            f'<audio id="bgm" data-start="0" '
            f'data-duration="{total}" data-track-index="1" data-volume="{BGM_VOL}" '
            f'src="audio/bgm.mp3"></audio>'
        )

    bubbles_html = []
    audio_html = []
    tweens = []
    for i, (ln, start) in enumerate(zip(lines, starts)):
        role = "ai" if ln["role"] == "ai" else "user"
        name = html.escape(ln.get("name", ln["speaker"]))
        raw_text = _strip(ln["text"])
        text_spans = _split_to_spans(raw_text)
        bid = f"b{i}"
        tid = f"t{i}"
        bubbles_html.append(
            f'<div class="bubble {role}" id="{bid}">'
            f'<div class="bubble-name">{name}</div>'
            f'<span class="bubble-text" id="{tid}">{text_spans}</span></div>'
        )
        audio_html.append(
            f'<audio id="a{i}" data-start="{start}" '
            f'data-duration="{round(ln["duration_ms"]/1000, 3)}" '
            f'data-track-index="{10+i}" data-volume="1" '
            f'src="audio/{ln["file"]}"></audio>'
        )
        # 计算打字速度：用语音时长的 70% 来打完所有字
        char_count = max(len(raw_text), 1)
        audio_dur = ln["duration_ms"] / 1000.0
        stagger = round((audio_dur * 0.65) / char_count, 4)
        stagger = max(min(stagger, 0.18), 0.03)  # 限制在 0.03~0.18 秒/字

        # 气泡轻量入场 + 文字打字机效果
        tweens.append(
            f'tl.set("#{bid}", {{display:"block"}}, {start});\n'
            f'  tl.from("#{bid}", {{y:10, opacity:0, scale:0.98, '
            f'duration:{ENTER_DUR}, ease:"power2.out"}}, {start});\n'
            f'  tl.to("#{tid} .c", {{opacity:1, stagger:{stagger}, duration:0.01}}, {start + 0.05});'
        )

    title = html.escape(story.get("title", ""))
    subtitle = html.escape(story.get("subtitle", ""))

    html_doc = _TEMPLATE.format(
        title=title,
        subtitle=subtitle,
        width=W, height=H,
        duration=total,
        bubbles="\n        ".join(bubbles_html),
        audios="\n  ".join([bgm_audio_html] + audio_html) if bgm_audio_html else "\n  ".join(audio_html),
        tweens="\n  ".join(tweens),
    )
    (comp_dir / "index.html").write_text(html_doc, encoding="utf-8")
    return comp_dir


_TEMPLATE = """<!doctype html>
<html><head><meta charset="utf-8"><title>{title}</title>
<style>
  html,body {{ margin:0; padding:0; background:#0d0d0d; }}
  #dialogue-video {{
    position: relative; width: {width}px; height: {height}px;
    background: radial-gradient(ellipse at 50% 30%, #1f1f1f 0%, #0a0a0a 70%);
    font-family: 'PingFang SC', 'Helvetica Neue', sans-serif;
    overflow: hidden;
  }}
  .stage {{
    position: absolute; inset: 0;
    display: flex; flex-direction: column; align-items: center;
    padding: 120px 60px 80px;
    box-sizing: border-box;
  }}
  .title {{ color:#f0f0f0; font-size: 44px; font-weight: 500; margin-bottom: 8px; }}
  .subtitle {{ color:#777; font-size: 22px; margin-bottom: 40px; }}
  .phone {{
    width: 880px; flex: 1;
    background: #fff; border-radius: 28px;
    box-shadow: 0 8px 60px rgba(0,0,0,.5);
    overflow: hidden;
    display: flex; flex-direction: column;
  }}
  .phone-header {{
    padding: 24px 32px; border-bottom: 1px solid #f0ede6;
    display: flex; align-items: center; justify-content: space-between;
    background: #fff; flex-shrink: 0;
  }}
  .phone-app {{ font-size: 22px; font-weight: 500; color: #aaa; }}
  .phone-date {{ font-size: 18px; color: #bbb; }}
  .messages {{
    flex: 1; padding: 28px 32px;
    display: flex; flex-direction: column; justify-content: flex-end;
    gap: 16px; overflow: hidden; background: #fff;
  }}
  .bubble {{
    display: none;
    max-width: 78%; padding: 18px 24px; border-radius: 22px;
    font-size: 28px; line-height: 1.5; color: #1a1a1a;
  }}
  .bubble-name {{ font-size: 18px; font-weight: 500; margin-bottom: 6px; }}
  .bubble-text {{ display: inline; }}
  .bubble-text .c {{ opacity: 0; display: inline-block; }}
  .bubble.ai {{ background: #f5f4f0; align-self: flex-start; border-bottom-left-radius: 6px; }}
  .bubble.ai .bubble-name {{ color: #aaa; }}
  .bubble.user {{ background: #1a1a1a; color: #f0f0f0; align-self: flex-end; border-bottom-right-radius: 6px; }}
  .bubble.user .bubble-name {{ color: #888; text-align: right; }}
</style>
</head>
<body>
<div id="dialogue-video" data-composition-id="dialogue-video" data-start="0"
     data-width="{width}" data-height="{height}" data-duration="{duration}">
  <div class="stage">
    <div class="title">{title}</div>
    <div class="subtitle">{subtitle}</div>
    <div class="phone">
      <div class="phone-header">
        <div class="phone-app">助理</div>
        <div class="phone-date"></div>
      </div>
      <div class="messages" id="messages">
        {bubbles}
      </div>
    </div>
  </div>

  {audios}

  <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
  <script>
    window.__timelines = window.__timelines || {{}};
    const tl = gsap.timeline({{paused: true}});
    {tweens}
    window.__timelines["dialogue-video"] = tl;
  </script>
</div>
</body></html>
"""
