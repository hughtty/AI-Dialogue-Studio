"""
Calls 风格波形视频生成器 · 原型版
用法：
  python waveform_generator.py --audio input.mp3 --subtitles subtitles.json --output output.mp4

字幕 JSON 格式：
[
  { "start": 0.0, "end": 4.5, "speaker": "助理", "text": "今天是您父亲六十八岁生日。" },
  { "start": 5.0, "end": 7.0, "speaker": "陈绍明", "text": "就说年底吧。" }
]
"""

import argparse
import json
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import librosa
from moviepy.editor import VideoClip, AudioFileClip

# ── 画面参数 ────────────────────────────────────────────────
WIDTH        = 1080
HEIGHT       = 1920
FPS          = 30
BG_COLOR     = (8, 8, 8)

# 波形
BAR_COUNT    = 64
BAR_W        = 10
BAR_GAP      = 5
BAR_MAX_H    = 320    # 最大振幅高度（像素）
BAR_MIN_H    = 6      # 静音时的最小高度
WAVE_CENTER  = HEIGHT // 2 - 60

# 颜色：助理=白，人物=灰
COLOR_AI     = (240, 240, 240)
COLOR_HUMAN  = (160, 160, 160)

# 字体
FONT_PATH    = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
FONT_SPEAKER = ImageFont.truetype(FONT_PATH, 28)
FONT_TEXT    = ImageFont.truetype(FONT_PATH, 42)

# 打字机：每秒显示的字符数
TYPEWRITER_CPS = 12

# ── 音频分析 ─────────────────────────────────────────────────
def analyze_audio(audio_path):
    """返回每帧的频带能量数组 shape=(n_frames, BAR_COUNT)"""
    y, sr = librosa.load(audio_path, sr=None, mono=True)
    duration = len(y) / sr
    n_frames = math.ceil(duration * FPS)
    samples_per_frame = int(sr / FPS)

    frame_bars = []
    for i in range(n_frames):
        chunk = y[i * samples_per_frame:(i + 1) * samples_per_frame]
        if len(chunk) == 0:
            frame_bars.append(np.zeros(BAR_COUNT))
            continue
        # 把每帧分成 BAR_COUNT 个频段，取 RMS
        sub = np.array_split(np.abs(chunk), BAR_COUNT)
        bars = np.array([np.sqrt(np.mean(s ** 2)) if len(s) > 0 else 0 for s in sub])
        frame_bars.append(bars)

    frame_bars = np.array(frame_bars)
    # 全局归一化
    peak = frame_bars.max()
    if peak > 0:
        frame_bars /= peak
    return frame_bars, duration

# ── 字幕查找 ──────────────────────────────────────────────────
def get_subtitle(subtitles, t):
    """返回当前时间 t 对应的字幕条目，无则返回 None"""
    for s in subtitles:
        if s["start"] <= t < s["end"]:
            return s
    return None

def typewriter_text(text, t, start):
    """打字机效果：返回当前应显示的字符数"""
    elapsed = t - start
    n = int(elapsed * TYPEWRITER_CPS)
    return text[:min(n, len(text))]

# ── 单帧渲染 ──────────────────────────────────────────────────
def render_frame(bars, subtitle, t):
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # 确定波形颜色（根据当前说话者）
    if subtitle and subtitle["speaker"] == "陈绍明":
        bar_color = COLOR_HUMAN
    else:
        bar_color = COLOR_AI

    # 波形：对称双向（上下镜像）
    total_w = BAR_COUNT * (BAR_W + BAR_GAP) - BAR_GAP
    x0 = (WIDTH - total_w) // 2

    for i, amp in enumerate(bars):
        h = int(amp * BAR_MAX_H) + BAR_MIN_H
        x = x0 + i * (BAR_W + BAR_GAP)
        # 上
        draw.rectangle([x, WAVE_CENTER - h, x + BAR_W, WAVE_CENTER - BAR_MIN_H], fill=bar_color)
        # 下
        draw.rectangle([x, WAVE_CENTER + BAR_MIN_H, x + BAR_W, WAVE_CENTER + h], fill=bar_color)

    # 中心基线
    draw.rectangle([x0, WAVE_CENTER - 1, x0 + total_w, WAVE_CENTER + 1],
                   fill=(40, 40, 40))

    if subtitle:
        speaker = subtitle["speaker"]
        text    = typewriter_text(subtitle["text"], t, subtitle["start"])

        # 说话者名字（左下角）
        draw.text((72, HEIGHT - 260), speaker, font=FONT_SPEAKER,
                  fill=(100, 100, 100))

        # 台词主文本（居中，波形下方）
        text_y = WAVE_CENTER + BAR_MAX_H + 80
        # 自动换行
        lines = wrap_text(text, FONT_TEXT, WIDTH - 160)
        for i, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=FONT_TEXT)
            tw = bbox[2] - bbox[0]
            draw.text(((WIDTH - tw) // 2, text_y + i * 58), line,
                      font=FONT_TEXT, fill=(220, 220, 220))

    return np.array(img)

def wrap_text(text, font, max_width):
    """简单按字符宽度换行"""
    lines, line = [], ""
    for char in text:
        test = line + char
        bbox = ImageDraw.Draw(Image.new("RGB", (1, 1))).textbbox((0, 0), test, font=font)
        if bbox[2] > max_width and line:
            lines.append(line)
            line = char
        else:
            line = test
    if line:
        lines.append(line)
    return lines

# ── 主流程 ────────────────────────────────────────────────────
def generate(audio_path, subtitles_path, output_path):
    print("分析音频...")
    frame_bars, duration = analyze_audio(audio_path)

    print("加载字幕...")
    with open(subtitles_path, "r", encoding="utf-8") as f:
        subtitles = json.load(f)

    print(f"渲染视频（时长 {duration:.1f}s，共 {len(frame_bars)} 帧）...")

    def make_frame(t):
        frame_idx = min(int(t * FPS), len(frame_bars) - 1)
        bars      = frame_bars[frame_idx]
        subtitle  = get_subtitle(subtitles, t)
        return render_frame(bars, subtitle, t)

    video = VideoClip(make_frame, duration=duration)
    audio = AudioFileClip(audio_path)
    video = video.set_audio(audio)

    video.write_videofile(
        output_path,
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        verbose=False,
        logger=None
    )
    print(f"完成：{output_path}")

# ── 测试模式：生成合成音频 + 字幕，验证渲染 ────────────────────
def run_demo():
    import soundfile as sf
    import os

    print("生成测试音频（合成正弦波模拟两段对话）...")
    sr = 22050
    # 模拟助理说话（3秒）
    t1 = np.linspace(0, 3, 3 * sr)
    seg1 = 0.4 * np.sin(2 * np.pi * 220 * t1) * np.exp(-t1 * 0.3)
    seg1 += 0.15 * np.random.randn(len(t1)) * np.exp(-t1 * 0.5)
    # 0.5秒静音
    silence = np.zeros(int(0.5 * sr))
    # 模拟陈绍明说话（2秒）
    t2 = np.linspace(0, 2, 2 * sr)
    seg2 = 0.3 * np.sin(2 * np.pi * 160 * t2) * np.exp(-t2 * 0.5)
    seg2 += 0.1 * np.random.randn(len(t2)) * np.exp(-t2 * 0.3)

    audio = np.concatenate([seg1, silence, seg2])

    audio_path = "/home/claude/demo_audio.wav"
    sf.write(audio_path, audio, sr)

    subtitles = [
        {"start": 0.0, "end": 3.0, "speaker": "助理",
         "text": "今天是您父亲六十八岁生日，转账已完成。"},
        {"start": 3.5, "end": 5.5, "speaker": "陈绍明",
         "text": "就说年底吧。"}
    ]
    sub_path = "/home/claude/demo_subtitles.json"
    with open(sub_path, "w", encoding="utf-8") as f:
        json.dump(subtitles, f, ensure_ascii=False, indent=2)

    generate(audio_path, sub_path, "/home/claude/demo_output.mp4")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio",     help="音频文件路径")
    parser.add_argument("--subtitles", help="字幕 JSON 文件路径")
    parser.add_argument("--output",    help="输出 MP4 路径", default="output.mp4")
    parser.add_argument("--demo",      action="store_true", help="运行内置演示")
    args = parser.parse_args()

    if args.demo or not args.audio:
        run_demo()
    else:
        generate(args.audio, args.subtitles, args.output)
