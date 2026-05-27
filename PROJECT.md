# Dialogue Studio — Project Overview

> 用一份文档把整个项目说清楚，给其他 AI 模型 / 协作者一次性看懂上下文。

---

## 1. 这是什么

**Dialogue Studio** 是一个 AI 对话体短故事创作平台。用户给一个主题，系统自动产出三件东西：

1. **故事文本**（JSON）— 多角色对话脚本，分卡片、有日期标注
2. **HTML 卡片**（图）— 模拟手机聊天界面的图文卡片，可单独导出/截图
3. **短视频**（MP4）— 逐句弹出的对话动画 + 同步语音，1080×1920 竖屏

目标用户是做"治愈向 / 陪伴感 / AI 与人类关系"主题短内容的创作者。核心定位：**从主题到成片的一条龙**，不是替代专业视频编辑器。

### 内容调性
- 5 张卡片，每张 3-6 轮对话
- 第 1 张立局 → 第 2 张埋裂缝 → 第 3 张积压张力 → 第 4 张转折引爆 → 第 5 张留白结局
- AI 角色克制精准，人类角色简短口语化
- 不说教，不点题，留给读者自己感受

---

## 2. 架构总览

项目当前**并存两条路径**，不是迭代关系：

| 分支 | 形态 | 用途 |
|---|---|---|
| `backend/`（实际文件平铺在根目录，按包式 import 引用） | FastAPI + SQLite + 单页 HTML 编辑器 | 完整产品形态：项目库、可视化编辑、音色配置、配音工作台 |
| `fast/` | 纯 Python CLI + 文件系统 | 极简实验线：用 Kimi + MiniMax + HyperFrames 一键出片，无 DB 无前端 |

两条线**完全隔离**，不互相 import。`fast/` 是为了快速验证"卡片对话弹出视频"这个产品形态用的，验证通过后再决定要不要把它的渲染管线反向接进 `backend/`。

---

## 3. 技术栈

### 共同栈
- **Python 3.12**（系统也有 3.9，但 `.pyc` 显示原本环境用的是 3.12）
- **httpx** 异步外部 API 调用
- **python-dotenv** 读 `.env`
- **Kimi K2.6**（Moonshot 平台）— 故事生成。`https://api.moonshot.cn/v1`，**完全兼容 OpenAI SDK**，只需把 `base_url` 切过去
- **MiniMax** — TTS（同步 `t2a_v2` + 异步 `t2a_async_v2`）、Voice Design、Voice Clone。模型 `speech-2.8-hd`

### `backend/` 专属
- **FastAPI 0.115** + **SQLAlchemy 2.x**（`Mapped` 写法）+ **SQLite**（`dialogue.db`）
- 单文件前端 `index.html`（原生 JS + CSS，无构建步骤）
- 与后端同源部署，FastAPI 直接 serve 静态文件，前端用相对路径调 `/api/*`

### `fast/` 专属
- **OpenAI SDK** 调 Kimi
- **PyYAML** 读 `voices.yml`
- **HyperFrames CLI**（`npx hyperframes`）— HTML composition → MP4 渲染管线
  - 需要 Node 22+ 和 FFmpeg
  - 首次运行会下载 Chromium

### 已声明但暂未启用
- **Celery / Redis** — 在 `requirements.txt` 和 `config.py` 里，原本规划做异步视频任务队列，目前未使用，Phase 3 倾向用 `asyncio` 后台任务替代
- **Alembic** — 已声明，但目前数据库迁移用裸 `ALTER TABLE` 手动跑

---

## 4. 开发阶段

按依赖关系拆四段，每段不能跨越：

| Phase | 范围 | 外部依赖 | 状态 |
|---|---|---|---|
| 0 | 工程基础（FastAPI 骨架、SQLite、项目/台词 CRUD） | 无 | ✅ 完成 |
| 1 | LLM 生成故事 + 卡片预览编辑器 | Kimi（曾是 Claude） | ✅ 完成 |
| 2 | MiniMax **同步** TTS 逐句配音 + 试听 | MiniMax | ✅ 完成（在 `backend/`） |
| 3 | 视频成片 | MiniMax 异步 TTS / HyperFrames | 🚧 当前阶段，方向已切换：原计划用异步 TTS + 自写 ffmpeg + 波形可视化；现改为 **HyperFrames + 对话弹出** |

Phase 3 的方向调整是关键决策：放弃异步 TTS 拿时间戳的链路（同步 TTS 已返回 `duration_ms`，足够驱动卡片入场动画），改用 HyperFrames 把 HTML 直接渲成 MP4。**结果：`fast/` 分支诞生**。

---

## 5. 目录结构

```
AI Dialogue Studio/
├── PROJECT.md            ← 你正在看的这份
├── agents.md             ← 给在本仓库写代码的 agent 看的协作规范
├── .env                  ← MOONSHOT_API_KEY / MINIMAX_API_KEY（gitignored）
├── .gitignore
├── requirements.txt
├── dialogue.db           ← SQLite（gitignored）
│
│ — backend/ 路径（文件实际平铺在根目录，按 backend.* 包路径 import）—
├── main.py               # FastAPI app 入口
├── config.py             # 环境变量、API key、路径常量
├── database.py           # SQLAlchemy engine / Session / init_db
├── project.py            # Project 模型（含 voices JSON 字段）
├── line.py               # Line 模型（audio_file/duration_ms/audio_status/error_msg）
├── video_job.py          # VideoJob 模型（Phase 3）
├── projects.py           # /api/projects/** 路由
├── story.py              # /api/story/** 路由（调用 services.story）
├── tts.py                # /api/tts/** 路由（preview / 单句 / 批量 SSE / 删音频）
├── health.py
├── storage.py            # 文件路径规范、_preview/ TTL 清理
├── minimax.py            # MiniMax 四接口薄封装
├── waveform_generator.py # 老 Phase 3 残留，未来可能弃用
├── calls_studio_app.py   # 早期单文件原型，参考用
├── index.html            # 前端单页（项目库 + 编辑器 + 配音工作台）
├── product_vision.html   # 产品文档/视觉稿
├── dialogue_dev_spec.html
│
├── storage/              # 用户数据（gitignored）
│   ├── {project_id}/audio/{line_id}.mp3
│   ├── {project_id}/video/{job_id}.mp4
│   └── _preview/{uuid}.mp3   # 试听音频，TTL 1h
│
│ — fast/ 极简分支 —
├── fast/
│   ├── README.md
│   ├── llm.py            # Kimi K2.6 调用（OpenAI SDK + base_url）
│   ├── tts.py            # MiniMax 同步 TTS（独立版，不依赖 backend）
│   ├── cards.py          # story.json → 静态 cards.html
│   ├── composition.py    # story.json + audio → HyperFrames composition
│   ├── make.py           # CLI 入口（story / audio / video / all）
│   ├── voices.yml        # speaker → voice_id 映射
│   └── outputs/{slug}/   # 每个故事一个目录（gitignored）
│       ├── story.json
│       ├── cards.html
│       ├── audio/{NN}.mp3 + lines.json
│       ├── composition/index.html + audio/
│       └── final.mp4
│
└── .agents/skills/       # 安装的 HyperFrames skills（hyperframes/, hyperframes-cli/, gsap/, ...）
```

> **目录布局警告**：`backend/` 包里的文件物理上是平铺在根目录的，但 `main.py` 等用 `from .core.config import ...` 这种相对包导入。这意味着原本是按 `backend/{core,models,routers,services}/` 子包结构组织的，但被压平了。运行时需要从父目录以模块方式启动（`python -m backend.main` 或 `uvicorn backend.main:app`），实际启动命令未在仓库内确认。

---

## 6. 核心数据模型

### `Project`
- `id` (uuid), `title`, `status` (`draft|voicing|video_pending|done`)
- `voices: JSON` — `{ speaker_name: { voice_id, speed, vol, pitch } }`
- 关联 `lines[]` 和 `video_jobs[]`

### `Line`
- `id`, `project_id`, `index`（顺序）
- `speaker`, `text_raw`（含 `<#0.3#>` 停顿标签）, `text_clean`（去标签）
- `audio_file`, `duration_ms`, `audio_status` (`pending|generating|done|error`), `error_msg`

### `VideoJob`（Phase 3）
- `id`, `project_id`, `tts_task_id`, `merged_audio`, `timestamps: JSON`, `video_file`, `status`
- 注：原设计假定异步 TTS 拿 timestamps；HyperFrames 路径下大部分字段会闲置

### `fast/` 的 story.json 结构
```json
{
  "title": "外地的周三晚上",
  "slug": "remote-wednesday-night",
  "subtitle": "所有对话记录均来自「助理」应用",
  "slides": [
    { "num": 1, "date": "2024年3月13日 周三 21:42",
      "messages": [
        {"role": "ai",   "name": "助理",   "text": "今天加班到几点？"},
        {"role": "user", "name": "陈绍明", "text": "刚到家。"}
      ]
    }
  ]
}
```

---

## 7. `fast/` 工作流详解

```bash
python -m fast.make all "下班路上的孤独感"
```

内部按四步：

```
[1] llm.generate_story(theme)          → outputs/{slug}/story.json
                                       → outputs/{slug}/cards.html
[2] tts.tts_sync per line              → outputs/{slug}/audio/{NN}.mp3
                                       → outputs/{slug}/audio/lines.json
[3] composition.build()                → outputs/{slug}/composition/index.html
                                         + composition/audio/* (拷贝)
[4] npx hyperframes render             → outputs/{slug}/final.mp4
```

**重跑规则（文件系统就是状态）**：
- 删 `story.json` → 重新走 LLM
- 删 `audio/{NN}.mp3` → 重新合成那一句
- 删 `composition/` → 重新生成 composition
- 删 `final.mp4` → 重新渲染

**视频形态（当前 v1）**：
- 1080×1920 竖屏，深色径向渐变背景
- 居中一张白底「手机」聊天卡
- 气泡按音频起点 `gsap.from({y:24, opacity:0, scale:0.96})` 弹入
- AI 气泡在左（米色），用户气泡在右（深色）
- 每条音频按 `data-start = 累计时长` 顺序播放
- 末尾留白 1 秒
- **没有波形、没有字幕、没有片头**

波形模式留作 v2 选项，做成 `composition.py` 的另一个变体。

---

## 8. `backend/` 工作流

### 故事生成
`POST /api/story/generate` → `services/story.py` 调 LLM → 写入数据库（清空旧 lines）→ 前端 reload。

### 配音（Phase 2 已落地）
- `POST /api/tts/preview` — 任意文本试听，文件落 `storage/_preview/{uuid}.mp3`
- `POST /api/tts/lines/{line_id}` — 单句配音
- `POST /api/tts/projects/{pid}/batch` — **SSE 流**，逐条推 `{type:"progress", line_id, status, audio_url, duration_ms}`
- `DELETE /api/tts/lines/{line_id}/audio` — 删音频 + 重置状态

并发控制：`asyncio.Semaphore(3)`。MiniMax 5xx 自动重试一次。SSE 中单句失败不中断整批，标 `error` + `error_msg` 继续。

### 前端配音工作台
- 每行台词右侧 ▶ 试听 + ↻ 重做 按钮
- 显示 `duration`（如 `2.3s` / `1:25`）
- 错误状态红色 + 行内 `⚠ error_msg`
- 右侧音色卡：每个 speaker 配 `voice_id / speed / vol / pitch`，附「试听」按钮
- 「生成配音」按钮用 SSE 实时刷进度条

---

## 9. 外部 API 集成要点

### Kimi (Moonshot)
- Base URL：`https://api.moonshot.cn/v1`
- Auth：`Authorization: Bearer $MOONSHOT_API_KEY`
- 模型 ID：`kimi-k2.6`（最新）、`kimi-k2.5`、`kimi-k2-thinking`、`moonshot-v1-128k`
- **完全兼容 OpenAI SDK**，直接 `OpenAI(api_key=..., base_url="https://api.moonshot.cn/v1")`
- **K2.6 限制**：`temperature` 只能等于 1（不传或传 1 都行，传其他值会 400）
- 支持 `response_format={"type":"json_object"}`、tool use、partial mode

### MiniMax
- Base URL：`https://api.minimaxi.com/v1`
- Auth：`Authorization: Bearer $MINIMAX_API_KEY`
- TTS 模型：`speech-2.8-hd`
- 同步 `/t2a_v2`：返回 base64 mp3 + `extra_info.audio_length`（毫秒）
- 异步 `/t2a_async_v2`：开 `timestamp_response: true` 拿句级时间戳（Phase 3 原计划用，现已弃）
- Voice Design / Voice Clone：自定义音色（未在 `fast/` 用）

### HyperFrames
- 安装方式：通过 `npx hyperframes` 即用即装，无需全局安装
- 输入：一个目录，里面有 `index.html`（必须含 `data-composition-id` 的根 div + `data-start="0"` + `data-width/height/duration`）
- 输出：MP4
- CLI：`init / lint / preview / render / transcribe / tts / doctor`
- 关键约束：
  - 时间轴属性写在 `data-*`：`data-start`、`data-duration`、`data-track-index`
  - 音频用独立 `<audio>`，不能用 `<video>` 带音
  - GSAP timeline 必须 `{paused: true}`，注册到 `window.__timelines["<comp-id>"]`
  - **不准** `Math.random` / `Date.now` / `repeat: -1` / 异步建 timeline
  - 多场景必须用 transitions，不许 jump cut；中间场景**不允许**用 `gsap.to({opacity:0})` 退场

---

## 10. 开发规范

### 通用
- 中文注释 OK，标识符英文
- API key 只从 `config.py` / `os.getenv()` 读，不硬编码
- 文件路径走 `services/storage.py` 或 `fast/composition.py` 的封装，不手拼
- 默认不写注释，只在约束、陷阱、非显而易见的决定处留一行

### 后端
- 路由只做参数校验和编排，业务逻辑在 `services/`
- 外部 API 用 `httpx.AsyncClient`，带超时
- 短请求用 `Depends(get_db)`；长任务（SSE、后台）自己 `SessionLocal()` 自管
- 业务错误 raise `HTTPException`；外部 API 5xx 返 502
- 加并发限流：`asyncio.Semaphore`（TTS 用 3）
- 加新字段必须在 PR 里写迁移 SQL

### 前端
- 所有 API 调用走 `api(method, path, body)` helper
- 用户输入一律 `escapeHtml`
- 长任务用 SSE 刷进度，不轮询
- 全局 `_audioEl`，同时只响一个

### 数据库迁移
- 暂无 Alembic
- SOP：改 model → PR 描述里写 ALTER → 本地 `sqlite3 dialogue.db "ALTER..."`

### Git
- commit 信息标 Phase：如 `Phase 2: 批量 TTS 支持 force 重做`
- 不提交 `dialogue.db`、`storage/`、`.env`、`fast/outputs/`、`__pycache__/`

---

## 11. 当前状态快照

**已完成**
- Phase 0 / 1 / 2 全部落地（`backend/`）
- `fast/` 分支搭建完成，dry-run 已通过 `npx hyperframes lint`（0 errors / 0 warnings）
- LLM 从 Claude 切到 Kimi K2.6 完成（OpenAI SDK 兼容）
- `.env` 已写入 `MOONSHOT_API_KEY` 和 `MINIMAX_API_KEY`

**进行中 / 待解决**
- `fast/voices.yml` 里的 voice_id 是占位值（`female-tianmei` 等系统音色名），需要换成你 MiniMax 账户下的真实 voice_id
- Kimi 生成的故事可能引入 `voices.yml` 没映射的角色名（例：刚刚那次生成里出现"周建平"，导致 audio 步骤报错退出）—— 解决思路有三：
  1. `voices.yml` 增加更多角色 / 提供默认兜底
  2. 在 `llm.py` 的 prompt 里限定角色名为 voices.yml 中的 keys
  3. 给 `make.py audio` 加一个"未知角色用默认 voice_id"的 flag
- HyperFrames 的视频渲染（步骤 4）尚未端到端实测，预计首次运行会下载 Chromium

**已知坑**
- 系统 Python 是 3.9，`.pyc` 显示项目原本用 3.12 — 跑 `backend/` 时如果遇到 SQLAlchemy 2 的 `Mapped` 语法问题，先确认 Python 版本
- `index.html` 里加 `error_msg` 字段后，旧库需要手动 `ALTER TABLE lines ADD COLUMN error_msg TEXT`

---

## 12. 给后续协作者的提示

1. **先决定走哪条线**。`backend/` 是可视化产品形态、`fast/` 是命令行实验形态。不要混改两边。
2. **`fast/` 分支的设计原则**：文件即状态、每步可重跑、不引入 DB、不依赖 `backend/`。任何"为了复用代码"想 `from backend import ...` 的冲动都要警惕，宁可拷贝。
3. **新加视频形态**就在 `fast/` 下复制一份 `composition.py` 改个名（如 `composition_waveform.py`），CLI 加 `--mode` 参数选择，不要在一个文件里塞所有形态。
4. **HyperFrames 的非协商规则**（见 `.agents/skills/hyperframes/SKILL.md`）必须遵守，特别是确定性（不准随机）、scene transitions、timeline 同步注册。违反任何一条都会让 render 出现非预期行为甚至失败。
5. **不要把 API key 写进任何 memory / 文档 / 注释 / commit message**。`.env` 是凭据该呆的地方。

---

## 13. 一句话总结

> 给一个主题，得到一份 JSON 故事 + 一张 HTML 卡片 + 一段 MP4 短视频。  
> 后端是 FastAPI 全形态产品；`fast/` 是用 Kimi 写故事、MiniMax 配音、HyperFrames 渲染的纯命令行最小可行管线。
