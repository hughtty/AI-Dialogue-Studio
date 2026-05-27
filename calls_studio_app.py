"""
Calls 风格对话视频生成器
运行：python app.py
浏览器访问：http://localhost:5050
"""

import os, json, uuid, math, tempfile, threading
import numpy as np
import librosa
import soundfile as sf
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import VideoClip, AudioFileClip
from flask import Flask, request, jsonify, send_file

app = Flask(__name__)
UPLOAD_DIR = os.path.join(tempfile.gettempdir(), "calls_studio")
os.makedirs(UPLOAD_DIR, exist_ok=True)

FONT_PATH = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"

# ── Video renderer ─────────────────────────────────────────────
W, H, FPS    = 1080, 1920, 30
N_BARS       = 64
BAR_W        = 10
BAR_GAP      = 5
BAR_MAX_H    = 300
BAR_MIN_H    = 5
CY           = H // 2 - 80
TW_CPS       = 10

def load_bars(path):
    y, sr = librosa.load(path, sr=None, mono=True)
    spf = max(1, int(sr / FPS))
    n   = math.ceil(len(y) / spf)
    out = []
    for i in range(n):
        chunk = y[i*spf:(i+1)*spf]
        if not len(chunk):
            out.append(np.zeros(N_BARS)); continue
        subs = np.array_split(np.abs(chunk), N_BARS)
        out.append(np.array([np.sqrt(np.mean(s**2)) if len(s) else 0 for s in subs]))
    out = np.array(out)
    pk = out.max()
    if pk > 0: out /= pk
    return out, len(y)/sr

def wrap(text, font, maxw, draw):
    lines, cur = [], ""
    for c in text:
        t = cur + c
        if draw.textbbox((0,0), t, font=font)[2] > maxw and cur:
            lines.append(cur); cur = c
        else:
            cur = t
    if cur: lines.append(cur)
    return lines

def draw_frame(bars, sub, t, fonts):
    img  = Image.new("RGB", (W, H), (6, 6, 6))
    d    = ImageDraw.Draw(img)
    col  = (255,255,255) if (not sub or sub["speaker"]=="助理") else (155,155,155)
    tw   = N_BARS*(BAR_W+BAR_GAP)-BAR_GAP
    x0   = (W-tw)//2
    for i, a in enumerate(bars):
        hh = int(a*BAR_MAX_H) + BAR_MIN_H
        x  = x0 + i*(BAR_W+BAR_GAP)
        d.rectangle([x, CY-hh, x+BAR_W, CY-BAR_MIN_H], fill=col)
        d.rectangle([x, CY+BAR_MIN_H, x+BAR_W, CY+hh], fill=col)
    d.rectangle([x0, CY-1, x0+tw, CY+1], fill=(30,30,30))
    if sub:
        n    = min(int((t-sub["start"])*TW_CPS), len(sub["text"]))
        txt  = sub["text"][:n]
        spkr = sub["speaker"]
        d.text((80, H-280), spkr, font=fonts["sm"], fill=(90,90,90))
        ty = CY + BAR_MAX_H + 90
        for li, ln in enumerate(wrap(txt, fonts["lg"], W-160, d)):
            bb = d.textbbox((0,0), ln, font=fonts["lg"])
            d.text(((W-(bb[2]-bb[0]))//2, ty+li*60), ln, font=fonts["lg"], fill=(215,215,215))
    return np.array(img)

def generate_video(rows, gap, out_path, cb=None):
    fonts = {
        "sm": ImageFont.truetype(FONT_PATH, 30),
        "lg": ImageFont.truetype(FONT_PATH, 44),
    }
    segs, sr0 = [], None
    for r in rows:
        y, sr = librosa.load(os.path.join(UPLOAD_DIR, r["audio"]), sr=sr0, mono=True)
        if not sr0: sr0 = sr
        segs.append(y)

    sil   = np.zeros(int(gap * sr0))
    parts, subs, t = [], [], 0.0
    for i, (y, r) in enumerate(zip(segs, rows)):
        dur = len(y)/sr0
        subs.append({"start": t, "end": t+dur, "speaker": r["speaker"], "text": r["text"]})
        parts.append(y)
        t += dur
        if i < len(segs)-1:
            parts.append(sil); t += gap

    combined = np.concatenate(parts)
    tmp_wav  = os.path.join(UPLOAD_DIR, f"_comb_{uuid.uuid4().hex}.wav")
    sf.write(tmp_wav, combined, sr0)

    frame_bars, duration = load_bars(tmp_wav)
    total = len(frame_bars)
    done  = [0]

    def get_sub(t):
        for s in subs:
            if s["start"] <= t < s["end"]: return s
        return None

    def make_frame(t):
        fi = min(int(t*FPS), len(frame_bars)-1)
        f  = draw_frame(frame_bars[fi], get_sub(t), t, fonts)
        done[0] += 1
        if cb and done[0] % FPS == 0: cb(done[0]/total)
        return f

    vc = VideoClip(make_frame, duration=duration)
    vc = vc.set_audio(AudioFileClip(tmp_wav))
    vc.write_videofile(out_path, fps=FPS, codec="libx264",
                       audio_codec="aac", verbose=False, logger=None)
    os.remove(tmp_wav)

# ── Flask routes ───────────────────────────────────────────────
progress_store = {}

@app.route("/")
def index():
    return HTML

@app.route("/audio/<fn>")
def serve_audio(fn):
    return send_file(os.path.join(UPLOAD_DIR, fn))

@app.route("/upload", methods=["POST"])
def upload():
    f    = request.files["file"]
    ext  = os.path.splitext(f.filename)[1]
    fn   = uuid.uuid4().hex + ext
    path = os.path.join(UPLOAD_DIR, fn)
    f.save(path)
    y, sr = librosa.load(path, sr=None, mono=True)
    return jsonify({"filename": fn, "duration": round(len(y)/sr, 2)})

@app.route("/generate", methods=["POST"])
def generate():
    data    = request.json
    job_id  = uuid.uuid4().hex
    out     = os.path.join(UPLOAD_DIR, f"out_{job_id}.mp4")

    def run():
        try:
            progress_store[job_id] = {"status": "processing", "p": 0}
            generate_video(data["rows"], float(data.get("gap", 0.3)), out,
                           lambda p: progress_store[job_id].update({"p": p}))
            progress_store[job_id] = {"status": "done", "p": 1}
        except Exception as e:
            progress_store[job_id] = {"status": "error", "msg": str(e)}

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"job_id": job_id})

@app.route("/progress/<job_id>")
def prog(job_id):
    return jsonify(progress_store.get(job_id, {"status": "unknown"}))

@app.route("/download/<job_id>")
def download(job_id):
    return send_file(os.path.join(UPLOAD_DIR, f"out_{job_id}.mp4"),
                     as_attachment=True, download_name="calls_output.mp4")

# ── HTML ───────────────────────────────────────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Calls Studio</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:ital,wght@0,300;0,400;0,500;1,300&family=DM+Sans:wght@300;400;500&display=swap');

*{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#080808;--bg2:#111;--bg3:#1a1a1a;--bg4:#222;
  --border:#2a2a2a;--border2:#333;
  --text:#e8e8e8;--text2:#888;--text3:#444;
  --accent:#fff;--accent2:#c8c8c8;
  --ai:#fff;--human:#888;
  --danger:#ff4444;--success:#44ff88;
  --r:8px;
}
html,body{height:100%;background:var(--bg);color:var(--text);
  font-family:'DM Sans',sans-serif;font-size:14px;line-height:1.5;overflow:hidden}

/* ── Layout ── */
.shell{display:grid;grid-template-rows:52px 1fr;height:100vh}
.topbar{display:flex;align-items:center;justify-content:space-between;
  padding:0 24px;border-bottom:1px solid var(--border);background:var(--bg)}
.topbar-left{display:flex;align-items:center;gap:16px}
.logo{font-family:'DM Mono',monospace;font-size:13px;letter-spacing:.12em;
  color:var(--text2);text-transform:uppercase}
.project-name{background:none;border:none;color:var(--text);font:500 15px 'DM Sans',sans-serif;
  outline:none;width:220px}
.project-name::placeholder{color:var(--text3)}
.topbar-right{display:flex;align-items:center;gap:10px}

.main{display:grid;grid-template-columns:1fr 380px;overflow:hidden}

/* ── Script panel ── */
.script-panel{display:flex;flex-direction:column;border-right:1px solid var(--border);overflow:hidden}
.panel-head{display:flex;align-items:center;justify-content:space-between;
  padding:14px 20px;border-bottom:1px solid var(--border);flex-shrink:0}
.panel-title{font-family:'DM Mono',monospace;font-size:11px;letter-spacing:.1em;
  color:var(--text2);text-transform:uppercase}
.rows-wrap{flex:1;overflow-y:auto;padding:0}
.rows-wrap::-webkit-scrollbar{width:4px}
.rows-wrap::-webkit-scrollbar-thumb{background:var(--border2);border-radius:2px}

/* ── Row ── */
.row{display:grid;grid-template-columns:36px 110px 1fr 200px 36px;
  align-items:start;gap:0;border-bottom:1px solid var(--border);
  padding:14px 16px;transition:background .15s}
.row:hover{background:var(--bg2)}
.row.playing{background:var(--bg3)}
.row-num{font-family:'DM Mono',monospace;font-size:11px;color:var(--text3);
  padding-top:4px;user-select:none}
.speaker-wrap{padding-right:10px}
.speaker-select{background:var(--bg3);border:1px solid var(--border);color:var(--text);
  font:400 13px 'DM Sans',sans-serif;padding:5px 8px;border-radius:var(--r);
  width:100%;outline:none;cursor:pointer}
.speaker-select:focus{border-color:var(--border2)}
.speaker-select option{background:var(--bg3)}
.text-area{background:none;border:none;color:var(--text);
  font:400 14px 'DM Sans',sans-serif;resize:none;outline:none;
  width:100%;min-height:44px;line-height:1.6;padding-right:12px}
.text-area::placeholder{color:var(--text3)}

/* ── Audio zone ── */
.audio-zone{display:flex;flex-direction:column;gap:6px}
.upload-btn{display:flex;align-items:center;justify-content:center;gap:6px;
  border:1px dashed var(--border2);border-radius:var(--r);padding:8px 10px;
  color:var(--text2);font-size:12px;cursor:pointer;transition:all .15s;
  background:none;width:100%}
.upload-btn:hover{border-color:var(--text2);color:var(--text)}
.upload-btn.has-audio{border-style:solid;border-color:var(--border);
  background:var(--bg3);color:var(--text)}
.audio-controls{display:flex;align-items:center;gap:6px}
.play-btn{width:26px;height:26px;border-radius:50%;border:1px solid var(--border2);
  background:none;color:var(--text2);cursor:pointer;display:flex;align-items:center;
  justify-content:center;transition:all .15s;flex-shrink:0}
.play-btn:hover{border-color:var(--text);color:var(--text)}
.play-btn.active{background:var(--text);color:var(--bg)}
.duration-badge{font-family:'DM Mono',monospace;font-size:11px;color:var(--text2)}
.waveform-mini{height:24px;flex:1;opacity:.6}

.del-btn{background:none;border:none;color:var(--text3);cursor:pointer;
  padding:4px;border-radius:4px;transition:color .15s;font-size:16px;line-height:1}
.del-btn:hover{color:var(--danger)}

/* ── Footer bar ── */
.add-row-area{padding:12px 16px;border-top:1px solid var(--border);flex-shrink:0}

/* ── Right panel ── */
.right-panel{display:flex;flex-direction:column;overflow:hidden;background:var(--bg)}
.timeline-section{flex:1;overflow:hidden;display:flex;flex-direction:column}
.panel-head2{padding:14px 20px;border-bottom:1px solid var(--border);flex-shrink:0;
  display:flex;align-items:center;justify-content:space-between}
.timeline-wrap{flex:1;overflow-y:auto;padding:20px}

/* ── Timeline ── */
.timeline{display:flex;height:56px;border-radius:var(--r);overflow:hidden;gap:1px;
  background:var(--border)}
.seg{display:flex;flex-direction:column;justify-content:center;padding:0 8px;
  min-width:20px;overflow:hidden;cursor:pointer;transition:filter .15s;position:relative}
.seg:hover{filter:brightness(1.3)}
.seg.ai{background:#1e1e1e}
.seg.human{background:#161616}
.seg-spk{font-family:'DM Mono',monospace;font-size:9px;letter-spacing:.06em;
  text-transform:uppercase;color:var(--text2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.seg-dur{font-family:'DM Mono',monospace;font-size:10px;color:var(--text3)}
.seg-bar{position:absolute;bottom:0;left:0;right:0;height:2px}
.seg.ai .seg-bar{background:var(--ai);opacity:.25}
.seg.human .seg-bar{background:var(--human);opacity:.2}

.timeline-labels{display:flex;margin-top:6px;position:relative;height:16px}
.tl-label{position:absolute;font-family:'DM Mono',monospace;font-size:9px;
  color:var(--text3);transform:translateX(-50%)}

.total-dur{font-family:'DM Mono',monospace;font-size:12px;color:var(--text2);margin-top:12px}

/* ── Generate section ── */
.generate-section{border-top:1px solid var(--border);padding:20px;flex-shrink:0}
.setting-row{display:flex;align-items:center;justify-content:space-between;
  margin-bottom:16px}
.setting-label{font-size:13px;color:var(--text2)}
.setting-val{font-family:'DM Mono',monospace;font-size:12px;color:var(--text)}
.gap-slider{-webkit-appearance:none;width:120px;height:2px;background:var(--border2);
  outline:none;border-radius:1px}
.gap-slider::-webkit-slider-thumb{-webkit-appearance:none;width:12px;height:12px;
  background:var(--text);border-radius:50%;cursor:pointer}

.gen-btn{width:100%;padding:12px;background:var(--text);color:var(--bg);
  border:none;border-radius:var(--r);font:500 14px 'DM Sans',sans-serif;
  cursor:pointer;transition:opacity .15s;letter-spacing:.02em}
.gen-btn:hover{opacity:.88}
.gen-btn:disabled{opacity:.3;cursor:default}

.progress-wrap{margin-top:12px;display:none}
.progress-wrap.show{display:block}
.progress-bar{height:2px;background:var(--border);border-radius:1px;overflow:hidden;
  margin-bottom:8px}
.progress-fill{height:100%;background:var(--text);transition:width .3s;width:0}
.progress-text{font-family:'DM Mono',monospace;font-size:11px;color:var(--text2)}

.download-btn{display:block;width:100%;padding:10px;border:1px solid var(--border2);
  border-radius:var(--r);text-align:center;color:var(--text);text-decoration:none;
  font-size:13px;margin-top:10px;transition:background .15s}
.download-btn:hover{background:var(--bg3)}

/* ── Buttons ── */
.btn{padding:7px 14px;border-radius:var(--r);border:1px solid var(--border2);
  background:none;color:var(--text2);font:400 13px 'DM Sans',sans-serif;
  cursor:pointer;transition:all .15s;display:inline-flex;align-items:center;gap:6px}
.btn:hover{color:var(--text);border-color:var(--border2)}
.btn-ghost{border-color:transparent}
.btn-ghost:hover{background:var(--bg3)}

/* ── Speaker colors ── */
[data-spk="助理"]{color:var(--ai)}
[data-spk="陈绍明"]{color:var(--human)}
</style>
</head>
<body>
<div class="shell">

<!-- Topbar -->
<div class="topbar">
  <div class="topbar-left">
    <span class="logo">Calls Studio</span>
    <input class="project-name" id="project-name" placeholder="项目名称..." value="备忘录">
  </div>
  <div class="topbar-right">
    <span id="total-badge" style="font-family:'DM Mono',monospace;font-size:12px;color:var(--text2)">— 总时长</span>
  </div>
</div>

<!-- Main -->
<div class="main">

  <!-- Script panel -->
  <div class="script-panel">
    <div class="panel-head">
      <span class="panel-title">对话脚本</span>
      <div style="display:flex;gap:6px">
        <button class="btn btn-ghost" onclick="importJSON()">导入 JSON</button>
        <input id="json-file-input" type="file" accept=".json" style="display:none" onchange="handleJSONImport(event)">
      </div>
    </div>
    <div class="rows-wrap" id="rows-container"></div>
    <div class="add-row-area">
      <button class="btn" onclick="addRow()" style="width:100%;justify-content:center">
        <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor"><path d="M6 1v10M1 6h10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
        添加台词
      </button>
    </div>
  </div>

  <!-- Right panel -->
  <div class="right-panel">
    <div class="timeline-section">
      <div class="panel-head2">
        <span class="panel-title" style="font-family:'DM Mono',monospace;font-size:11px;letter-spacing:.1em;color:var(--text2);text-transform:uppercase">时间轴</span>
      </div>
      <div class="timeline-wrap">
        <div class="timeline" id="timeline"></div>
        <div class="timeline-labels" id="tl-labels"></div>
        <div class="total-dur" id="total-dur-text"></div>
        <div style="margin-top:20px;font-size:12px;color:var(--text3);line-height:1.8">
          <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
            <span style="display:inline-block;width:24px;height:2px;background:var(--ai);opacity:.6"></span>
            <span>助理</span>
          </div>
          <div style="display:flex;align-items:center;gap:8px">
            <span style="display:inline-block;width:24px;height:2px;background:var(--human);opacity:.4"></span>
            <span>其他角色</span>
          </div>
        </div>
      </div>
    </div>

    <div class="generate-section">
      <div class="setting-row">
        <span class="setting-label">段间静音</span>
        <div style="display:flex;align-items:center;gap:10px">
          <input type="range" class="gap-slider" id="gap-slider"
            min="0" max="1.5" step="0.1" value="0.3"
            oninput="document.getElementById('gap-val').textContent=parseFloat(this.value).toFixed(1)+'s'">
          <span class="setting-val" id="gap-val">0.3s</span>
        </div>
      </div>
      <button class="gen-btn" id="gen-btn" onclick="startGenerate()" disabled>
        生成视频
      </button>
      <div class="progress-wrap" id="progress-wrap">
        <div class="progress-bar"><div class="progress-fill" id="progress-fill"></div></div>
        <div class="progress-text" id="progress-text">正在渲染...</div>
      </div>
      <a class="download-btn" id="download-btn" style="display:none" href="#" download>
        下载 MP4
      </a>
    </div>
  </div>

</div>
</div>

<audio id="audio-player" style="display:none"></audio>

<script>
// ── State ──────────────────────────────────────────────────────
let rows = [];
let playingId = null;
const SPEAKERS = ["助理", "陈绍明"];

function uid() { return Math.random().toString(36).slice(2,10); }

// ── Row management ─────────────────────────────────────────────
function addRow(data={}) {
  const r = {
    id: uid(),
    speaker: data.speaker || "助理",
    text: data.text || "",
    audio: data.audio || null,
    duration: data.duration || 0
  };
  rows.push(r);
  renderRows();
  updateTimeline();
  checkGenBtn();
  // Focus the new row's textarea
  setTimeout(() => {
    const ta = document.querySelector(`[data-id="${r.id}"] .text-area`);
    if(ta) ta.focus();
  }, 50);
}

function deleteRow(id) {
  rows = rows.filter(r => r.id !== id);
  renderRows();
  updateTimeline();
  checkGenBtn();
}

function updateRow(id, key, val) {
  const r = rows.find(r => r.id === id);
  if(r) { r[key] = val; updateTimeline(); checkGenBtn(); }
}

// ── Render rows ────────────────────────────────────────────────
function renderRows() {
  const c = document.getElementById("rows-container");
  c.innerHTML = rows.map((r, i) => `
    <div class="row${playingId===r.id?' playing':''}" data-id="${r.id}">
      <div class="row-num">${String(i+1).padStart(2,'0')}</div>
      <div class="speaker-wrap">
        <select class="speaker-select" onchange="updateRow('${r.id}','speaker',this.value);renderRows()">
          ${SPEAKERS.map(s=>`<option value="${s}"${r.speaker===s?' selected':''}>${s}</option>`).join('')}
          <option value="旁白"${r.speaker==='旁白'?' selected':''}>旁白</option>
        </select>
      </div>
      <textarea class="text-area" rows="2" placeholder="输入台词..."
        onchange="updateRow('${r.id}','text',this.value)"
        oninput="this.style.height='auto';this.style.height=this.scrollHeight+'px'"
      >${r.text}</textarea>
      <div class="audio-zone">
        ${r.audio ? `
          <button class="upload-btn has-audio" onclick="triggerUpload('${r.id}')">
            <svg width="11" height="11" viewBox="0 0 11 11" fill="none">
              <path d="M1 7.5L3.5 5l2 2L8 4l2 2.5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            ${r.audio.slice(0,16)}…
          </button>
          <div class="audio-controls">
            <button class="play-btn${playingId===r.id?' active':''}" onclick="togglePlay('${r.id}')">
              ${playingId===r.id
                ? '<svg width="8" height="9" fill="currentColor" viewBox="0 0 8 9"><rect x="0" y="0" width="3" height="9" rx="1"/><rect x="5" y="0" width="3" height="9" rx="1"/></svg>'
                : '<svg width="8" height="9" fill="currentColor" viewBox="0 0 8 9"><path d="M0 0l8 4.5L0 9z"/></svg>'
              }
            </button>
            <canvas class="waveform-mini" id="wm-${r.id}" width="120" height="24"></canvas>
            <span class="duration-badge">${r.duration.toFixed(1)}s</span>
          </div>
        ` : `
          <button class="upload-btn" onclick="triggerUpload('${r.id}')">
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <path d="M6 8V2M3.5 4.5L6 2l2.5 2.5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
              <path d="M1 9v1.5h10V9" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
            </svg>
            上传音频
          </button>
        `}
        <input type="file" accept="audio/*" style="display:none"
          id="fi-${r.id}" onchange="handleUpload('${r.id}',this)">
      </div>
      <button class="del-btn" onclick="deleteRow('${r.id}')">×</button>
    </div>
  `).join('');

  // Draw mini waveforms
  rows.filter(r=>r.audio && r.waveData).forEach(r => drawMiniWave(r));
}

function triggerUpload(id) {
  document.getElementById(`fi-${id}`)?.click();
}

// ── Audio upload ───────────────────────────────────────────────
async function handleUpload(id, input) {
  const file = input.files[0];
  if(!file) return;
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch("/upload", {method:"POST", body:fd});
  const data = await res.json();
  const r = rows.find(r=>r.id===id);
  if(r){
    r.audio = data.filename;
    r.duration = data.duration;
    // Load waveform data for mini preview
    const ab = await file.arrayBuffer();
    const ac = new AudioContext();
    const buf = await ac.decodeAudioData(ab);
    r.waveData = buildMiniWave(buf);
    ac.close();
  }
  renderRows();
  updateTimeline();
  checkGenBtn();
}

function buildMiniWave(buf) {
  const ch = buf.getChannelData(0);
  const N = 60, step = Math.floor(ch.length/N);
  const out = [];
  for(let i=0;i<N;i++){
    let sum=0;
    for(let j=0;j<step;j++) sum+=Math.abs(ch[i*step+j]||0);
    out.push(sum/step);
  }
  const pk = Math.max(...out)||1;
  return out.map(v=>v/pk);
}

function drawMiniWave(r) {
  const c = document.getElementById(`wm-${r.id}`);
  if(!c||!r.waveData) return;
  const ctx = c.getContext("2d");
  ctx.clearRect(0,0,c.width,c.height);
  const bw = c.width/r.waveData.length;
  const cy = c.height/2;
  ctx.fillStyle = playingId===r.id ? "rgba(255,255,255,0.7)" : "rgba(255,255,255,0.25)";
  r.waveData.forEach((v,i)=>{
    const h = Math.max(1, v*(cy-1));
    ctx.fillRect(i*bw+.5, cy-h, bw-.5, h*2);
  });
}

// ── Playback ───────────────────────────────────────────────────
function togglePlay(id) {
  const player = document.getElementById("audio-player");
  if(playingId === id) {
    player.pause(); playingId=null; renderRows(); return;
  }
  const r = rows.find(r=>r.id===id);
  if(!r?.audio) return;
  player.src = `/audio/${r.audio}`;
  player.play();
  playingId = id;
  player.onended = ()=>{ playingId=null; renderRows(); };
  renderRows();
}

// ── Timeline ───────────────────────────────────────────────────
function updateTimeline() {
  const tl = document.getElementById("timeline");
  const lb = document.getElementById("tl-labels");
  const td = document.getElementById("total-dur-text");
  const tb = document.getElementById("total-badge");
  const gap = parseFloat(document.getElementById("gap-slider").value);

  const total = rows.reduce((s,r)=>s+r.duration,0) + Math.max(0,rows.length-1)*gap;
  if(total===0){ tl.innerHTML="<div style='width:100%;background:var(--bg3);border-radius:var(--r);height:56px;display:flex;align-items:center;justify-content:center;color:var(--text3);font-size:12px'>上传音频后显示时间轴</div>"; lb.innerHTML=""; td.textContent=""; tb.textContent="—"; return; }

  tl.innerHTML = rows.map(r=>{
    if(!r.duration) return '';
    const pct = (r.duration/total*100).toFixed(2);
    const cls = r.speaker==="助理"?"ai":"human";
    return `<div class="seg ${cls}" style="width:${pct}%" title="${r.speaker}: ${r.text.slice(0,30)}…" onclick="scrollToRow('${r.id}')">
      <div class="seg-spk">${r.speaker}</div>
      <div class="seg-dur">${r.duration.toFixed(1)}s</div>
      <div class="seg-bar"></div>
    </div>`;
  }).join('');

  // Time labels
  let t=0, labels="";
  rows.forEach((r,i)=>{
    if(r.duration && total>0){
      const x=(t/total*100).toFixed(1);
      labels+=`<div class="tl-label" style="left:${x}%">${t.toFixed(1)}s</div>`;
      t+=r.duration+(i<rows.length-1?gap:0);
    }
  });
  lb.innerHTML = labels;
  td.textContent = `总时长  ${total.toFixed(1)}s`;
  tb.textContent = `${total.toFixed(1)}s`;
}

function scrollToRow(id) {
  const el = document.querySelector(`[data-id="${id}"]`);
  if(el) el.scrollIntoView({behavior:"smooth",block:"center"});
}

// ── Generate ───────────────────────────────────────────────────
function checkGenBtn() {
  const ok = rows.length>0 && rows.every(r=>r.audio);
  document.getElementById("gen-btn").disabled = !ok;
}

async function startGenerate() {
  const gap = parseFloat(document.getElementById("gap-slider").value);
  const payload = {
    rows: rows.map(r=>({speaker:r.speaker, text:r.text, audio:r.audio})),
    gap
  };
  document.getElementById("gen-btn").disabled = true;
  document.getElementById("progress-wrap").classList.add("show");
  document.getElementById("download-btn").style.display="none";
  document.getElementById("progress-fill").style.width="0";
  document.getElementById("progress-text").textContent="正在渲染...";

  const res = await fetch("/generate",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
  const {job_id} = await res.json();
  pollProgress(job_id);
}

function pollProgress(job_id) {
  const interval = setInterval(async()=>{
    const res = await fetch(`/progress/${job_id}`);
    const d = await res.json();
    if(d.status==="processing"){
      const pct = Math.round((d.p||0)*100);
      document.getElementById("progress-fill").style.width=pct+"%";
      document.getElementById("progress-text").textContent=`渲染中 ${pct}%`;
    } else if(d.status==="done"){
      clearInterval(interval);
      document.getElementById("progress-fill").style.width="100%";
      document.getElementById("progress-text").textContent="完成";
      const dl = document.getElementById("download-btn");
      dl.href = `/download/${job_id}`;
      dl.style.display="block";
      document.getElementById("gen-btn").disabled=false;
    } else if(d.status==="error"){
      clearInterval(interval);
      document.getElementById("progress-text").textContent="错误："+d.msg;
      document.getElementById("gen-btn").disabled=false;
    }
  }, 800);
}

// ── JSON import ────────────────────────────────────────────────
function importJSON() {
  document.getElementById("json-file-input").click();
}

function handleJSONImport(e) {
  const file = e.target.files[0];
  if(!file) return;
  const reader = new FileReader();
  reader.onload = ev => {
    try {
      const data = JSON.parse(ev.target.result);
      const slides = data.slides || data;
      rows = [];
      (Array.isArray(slides)?slides:[]).forEach(s=>{
        (s.messages||[]).forEach(m=>{
          rows.push({id:uid(), speaker:m.name||m.role, text:m.text, audio:null, duration:0});
        });
      });
      renderRows(); updateTimeline(); checkGenBtn();
    } catch(err){ alert("JSON 格式错误"); }
  };
  reader.readAsText(file);
}

// ── Gap slider ─────────────────────────────────────────────────
document.getElementById("gap-slider").addEventListener("input", updateTimeline);

// ── Init with sample rows ──────────────────────────────────────
[
  {speaker:"助理", text:"今天是您父亲六十八岁生日。转账已完成，稍后我会致电祝他生日快乐。"},
  {speaker:"陈绍明", text:"就说年底吧。"},
  {speaker:"助理", text:"好的。还有其他需要我转达的吗？"},
].forEach(r=>addRow(r));

updateTimeline();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    print("启动 Calls Studio → http://localhost:5050")
    app.run(debug=False, port=5050, threaded=True)
