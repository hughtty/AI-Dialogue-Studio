# Dialogue Studio — Agents Guide

给 AI 协作者看的项目说明。目的是让下一个进来写代码的人（或 agent）在 5 分钟内理解上下文、找到文件、按规范改东西。

---

## 1. 产品背景

**Dialogue Studio** 是一个 AI 对话体故事创作平台。用户给一个主题，系统自动：

1. 用 Claude 生成一段多角色对话脚本（分卡片、有旁白、带停顿标签）
2. 在编辑器里手工打磨台词、配置音色
3. 用 MiniMax TTS 给每句台词生成语音
4. 合并音频 + 波形可视化，导出成一段短视频

目标用户是做「治愈向 / 陪伴感 / 短故事」内容的创作者。核心卖点是**从主题到成片的一条龙**，而不是替代编辑器。

---

## 2. 开发阶段（Phase）

项目按依赖关系拆成四段，已完成 / 在做的都要在 PR 说明里标清楚：

| Phase | 范围 | 外部依赖 | 状态 |
|---|---|---|---|
| 0 | 工程基础（FastAPI 骨架、SQLite、项目/台词 CRUD） | 无 | ✅ 已完成 |
| 1 | Claude 生成故事 + 卡片预览编辑器 | Claude API | ✅ 已完成 |
| 2 | MiniMax **同步** TTS 逐句配音 + 试听 | MiniMax API | 🚧 当前阶段 |
| 3 | MiniMax **异步** TTS（带时间戳）+ 波形视频合成 | MiniMax API、ffmpeg | ⏳ 待做 |

**不要跨 Phase 提前写代码**。Phase 3 的字段（`VideoJob.timestamps` 等）Phase 2 里可以留空但不能依赖。

---

## 3. 技术栈

**后端**
- Python 3.12 + FastAPI
- SQLAlchemy 2.x（`Mapped` / `mapped_column` 写法）+ SQLite（`dialogue.db`）
- `httpx` 异步调外部 API
- 文件存储：本地磁盘（`storage/` 目录），通过 `/storage/*` 路由 serve
- 无 Celery（Phase 3 视频渲染会用 `asyncio` 后台任务，不上 Celery；`config.py` 里的 Celery 配置目前闲置）

**前端**
- 单文件 `index.html`，原生 JS + CSS，无构建步骤
- 与后端**同源部署**（FastAPI 直接 serve 静态文件），所以 API 调用用相对路径 `/api/...`
- 批量进度用 `fetch` + `ReadableStream` 解析 SSE，没引额外库

**外部服务**
- **Claude API** — 故事生成（`services/story.py`）
- **MiniMax API** — TTS 同步 / 异步 / Voice Design / Voice Clone（`services/minimax.py`）
  - 同步 TTS：`t2a_v2`，返回 base64 音频 + `extra_info.audio_length`
  - 异步 TTS：`t2a_async_v2`，开 `timestamp_response` 拿句级时间戳
  - 模型：`speech-2.8-hd`（config 里写死）

---

## 4. 代码结构

```
backend/
├── core/
│   ├── config.py        # 读环境变量，所有常量集中在这
│   └── database.py      # SQLAlchemy engine / Session / Base / init_db
├── models/              # 数据库模型
│   ├── project.py       # 项目（含 voices JSON 字段）
│   ├── line.py          # 台词行（audio_file / duration_ms / audio_status / error_msg）
│   └── video_job.py     # 视频任务（Phase 3）
├── routers/             # FastAPI 路由
│   ├── projects.py      # 项目与台词 CRUD
│   ├── story.py         # Claude 故事生成 / 导入
│   ├── tts.py           # MiniMax 同步 TTS（Phase 2）
│   └── health.py
├── services/            # 业务逻辑 + 外部集成
│   ├── story.py         # 调 Claude
│   ├── minimax.py       # 调 MiniMax（四个接口的薄封装）
│   └── storage.py       # 文件路径规范、预览清理
└── main.py              # FastAPI app、中间件、静态挂载

storage/                 # 用户数据（gitignore）
├── {project_id}/audio/{line_id}.mp3
├── {project_id}/video/{job_id}.mp4
└── _preview/{uuid}.mp3  # 试听音频，TTL 1h

index.html               # 前端单页
dialogue.db              # SQLite 数据库（gitignore）
.env                     # MINIMAX_API_KEY / CLAUDE_API_KEY（gitignore）
```

---

## 5. 关键领域概念

- **Project** — 一个故事。有 `title / status / voices`。`voices` 是 `{speaker: {voice_id, speed, vol, pitch}}`。
- **Line** — 一条台词。有 `index`（顺序）、`speaker`、`text_raw`（含 `<#0.3#>` 停顿标签）、`text_clean`（去标签，展示和送 TTS 用）。配音状态 `audio_status ∈ {pending, generating, done, error}`。
- **Slide** — 只是前端分组概念（UI 上把连续台词切成卡片），**数据库里不存**，每次 `buildSlides()` 重算。
- **voice_id** — MiniMax 的音色 ID，可以是系统音色 / Voice Design 生成的 / Voice Clone 克隆的。Phase 2 前只要求手填。
- **停顿标签** — `<#数字#>` 插在台词里，交给 MiniMax 做停顿。`strip_tags()` 去标签后才是展示文本。

---

## 6. 开发规范

### 通用
- 中文注释和用户提示 OK，代码标识符用英文
- 外部 API key 只从 `config.py` 读，不直接 `os.getenv()` 散落各处
- 文件路径统一走 `services/storage.py`，不手拼 `storage/.../audio/...`
- 默认不写注释。只在约束、陷阱、非显而易见的决定处写一行

### 后端
- 路由文件只做参数校验和编排，业务逻辑放 `services/`
- 所有外部 API 调用用 `httpx.AsyncClient`，带超时
- DB session：短请求用 `Depends(get_db)`；长任务（SSE、后台）用 `SessionLocal()` 自己开，自己关
- 错误：业务错误 raise `HTTPException`；外部 API 5xx 返回 502 并带简短信息
- 并发外部 API 时加 `asyncio.Semaphore` 限流（TTS 用 3）
- 新加模型字段时**必须提供迁移 SQL**（写在 PR 里），不依赖 `init_db()` 重建

### 前端
- 所有 API 调用走 `api(method, path, body)` helper
- 渲染后重新绑定的 DOM 引用要 re-query，不要缓存 element
- 长任务用 SSE 刷进度（`progress-fill` + `progress-text`），不要轮询
- 用户输入一律 `escapeHtml`，特别是 `error_msg`、`speaker` 这种来源可变的字段
- 音频播放统一用全局 `_audioEl` + `playUrl(url)`，保证同一时间只响一个

### 数据库迁移
- 暂无 Alembic。加字段的 SOP：
  1. 改 model 文件
  2. PR 描述里写一行 `ALTER TABLE ... ADD COLUMN ...;`
  3. 本地 `sqlite3 dialogue.db "ALTER ..."` 跑一遍
- 上 Alembic 是 Phase 3 之后的事，现在别过早引入

### Git
- 提交信息用中文或英文都行，但要说清 Phase：如 `Phase 2: 批量 TTS 支持 force 重做`
- 不提交 `dialogue.db`、`storage/`、`.env`、`__pycache__/`

---

## 7. 当前已知状态（随时更新）

- **Phase 2 刚落地**：`tts.py` 路由、`line.error_msg` 字段、前端试听 + 单句 + 批量 SSE 都已接通
- 尚未做：音色卡的 Voice Design / Voice Clone（Phase 2.5 可选）、视频合成（Phase 3）
- DB 如是旧库，需执行：`sqlite3 dialogue.db "ALTER TABLE lines ADD COLUMN error_msg TEXT;"`

---

## 8. 调试入口

- 后端日志：启动 uvicorn 的控制台
- 前端：浏览器 DevTools Console / Network
- TTS 失败看两处：①后端控制台的 MiniMax 响应 ②`Line.error_msg` 字段
- 音频直链：`http://localhost:8000/storage/{project_id}/audio/{line_id}.mp3`
