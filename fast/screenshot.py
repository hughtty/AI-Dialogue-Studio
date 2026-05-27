"""
fast/screenshot.py — 用 Chrome headless 批量截取小红书截图。
输出：900×1200（1x），通过 --force-device-scale-factor=2 可输出 1800×2400（2x）。
"""
import subprocess
import sys
from pathlib import Path
from typing import Optional

_CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
]


def _find_chrome() -> Optional[str]:
    for c in _CHROME_CANDIDATES:
        if Path(c).exists():
            return c
    # 尝试 which
    import shutil
    return shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chrome")


def screenshot_html(html_path: Path, png_path: Path, width: int = 900, height: int = 1200) -> None:
    """用 Chrome headless 截取单张 HTML 为 PNG。"""
    chrome = _find_chrome()
    if not chrome:
        raise RuntimeError("找不到 Chrome/Chromium，请安装 Google Chrome")

    cmd = [
        chrome,
        "--headless",
        f"--screenshot={png_path}",
        f"--window-size={width},{height}",
        "--hide-scrollbars",
        "--force-device-scale-factor=2",
        "--disable-gpu",
        "--no-sandbox",
        f"file://{html_path.absolute()}",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"Chrome screenshot 失败: {result.stderr}")
    if not png_path.exists():
        raise RuntimeError(f"Chrome 未生成截图文件: {png_path}")


def batch_screenshots(slug: str) -> list[Path]:
    """为指定 story 批量生成小红书截图。"""
    from . import xiaohongshu_cards

    root = Path(__file__).parent
    outputs = root / "outputs" / slug
    story_path = outputs / "story.json"
    if not story_path.exists():
        sys.exit(f"找不到 {story_path}，先跑 story")

    import json
    story = json.loads(story_path.read_text(encoding="utf-8"))

    # 生成截图 HTML
    html_dir = outputs / "screenshots" / "html"
    html_paths = xiaohongshu_cards.write_screenshots(story, html_dir)

    # 截取 PNG
    png_dir = outputs / "screenshots" / "png"
    png_dir.mkdir(parents=True, exist_ok=True)
    png_paths: list[Path] = []

    print(f"[screenshots] 开始截取 {len(html_paths)} 张小红书截图…")
    for i, html_path in enumerate(html_paths):
        png_path = png_dir / f"{i+1:02d}.png"
        if png_path.exists():
            print(f"[screenshots] {i+1:02d}.png 已存在，跳过")
        else:
            print(f"[screenshots] 截取 {i+1:02d}.png …")
            screenshot_html(html_path, png_path)
        png_paths.append(png_path)

    print(f"[screenshots] ✓ {len(png_paths)} 张截图 → {png_dir.relative_to(root.parent)}")
    return png_paths
