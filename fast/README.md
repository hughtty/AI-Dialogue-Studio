# fast/ — 极简分支

不依赖 `backend/`，不连数据库，纯命令行 + 文件系统。

## 三个产物

每个故事 = `outputs/{slug}/` 目录，三步生成：

| 想要 | 命令 | 产物 |
|---|---|---|
| ① 文案 | `python -m fast.make story "<主题>"` | `story.json` + `cards.html` |
| ② 卡片 | （①已生成，浏览器打开 `cards.html`） | 静态预览页 |
| ③ 视频 | `python -m fast.make video <slug>` | `final.mp4` |

或者一把梭：
```bash
python -m fast.make all "下班路上的孤独感"
```

## 完整流程

```bash
# 1. 准备：项目根 .env 写好 MOONSHOT_API_KEY（Kimi）和 MINIMAX_API_KEY
# 2. 编辑 fast/voices.yml，把每个 speaker 映射到 MiniMax voice_id

# 3. 三步走（可以分开重跑）
python -m fast.make story "下班路上的孤独感"   # 生成 outputs/<slug>/{story.json,cards.html}
python -m fast.make audio <slug>              # 生成 audio/*.mp3 + lines.json
python -m fast.make video <slug>              # 生成 composition/ + final.mp4
```

## 重跑规则

- 想换文案：删 `story.json` 重跑 story
- 想换音色：删整个 `audio/` 重跑 audio（单条不存在时才合成，所以删指定 mp3 也可）
- 想换动画：删 `composition/` 和 `final.mp4`，重跑 video

## 视频模式

当前只有"卡片对话弹出"模式（竖屏 1080x1920，气泡按 TTS 时长依次入场）。
波形模式留待后续，作为另一个 composition.py 变体。

## 渲染依赖

需要 Node 22+ 和 FFmpeg（`npx hyperframes doctor` 自检）。
默认用 `--quality draft` 出片快，最终交付改 `--quality high`。
