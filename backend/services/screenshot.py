"""
services/screenshot.py — Chrome headless 截图（复用 fast/screenshot.py 逻辑，适配 backend）。
"""
import shutil
import subprocess
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
    return shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chrome")


def screenshot_html(html_path: Path, png_path: Path, width: int = 900, height: int = 1200) -> None:
    """用 Chrome headless 截取单张 HTML 为 PNG。"""
    chrome = _find_chrome()
    if not chrome:
        raise RuntimeError("找不到 Chrome/Chromium，请安装 Google Chrome")

    # 确保输出目录存在
    png_path.parent.mkdir(parents=True, exist_ok=True)

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


def batch_screenshots(html_paths: list[Path], png_dir: Path, force: bool = False) -> list[Path]:
    """批量截取 PNG，返回生成的文件路径列表。
    force=True 时覆盖已存在的 PNG。
    """
    png_dir.mkdir(parents=True, exist_ok=True)
    png_paths = []
    for i, html_path in enumerate(html_paths):
        png_path = png_dir / f"{i + 1:02d}.png"
        if force and png_path.exists():
            png_path.unlink()
        if png_path.exists():
            png_paths.append(png_path)
            continue
        screenshot_html(html_path, png_path)
        png_paths.append(png_path)
    return png_paths


def screenshot_single(html_path: Path, png_path: Path, force: bool = False) -> Path:
    """截取单张 HTML 为 PNG，返回路径。"""
    if force and png_path.exists():
        png_path.unlink()
    if not png_path.exists():
        screenshot_html(html_path, png_path)
    return png_path
