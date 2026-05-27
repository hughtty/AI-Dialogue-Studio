"""
services/story.py — 调用 Kimi K2.6 (Moonshot) 生成对话故事 JSON
生成内容包含：角色音色分配、逐句情感标注、语气词与停顿标签。
"""
import asyncio
import json
import re
from openai import AsyncOpenAI, RateLimitError

from ..core.config import MOONSHOT_API_KEY, MOONSHOT_BASE_URL, MOONSHOT_MODEL

_client = AsyncOpenAI(
    api_key=MOONSHOT_API_KEY,
    base_url=MOONSHOT_BASE_URL,
)

VOICE_CATALOG = """
【中文音色库】按角色类型选 voice_id：

AI 助理（克制、温暖、有距离感）：
  Chinese (Mandarin)_Warm_Girl — 温暖少女
  Chinese (Mandarin)_Gentle_Youth — 温润青年
  Chinese (Mandarin)_Crisp_Girl — 清脆少女（略带疏离）
  Robot_Armor — 机械战甲（明显的AI质感）

中年男性（疲惫、沧桑、有故事）：
  Chinese (Mandarin)_Sincere_Adult — 真诚青年（偏疲惫）
  Chinese (Mandarin)_Gentleman — 温润男声（成熟内敛）
  Chinese (Mandarin)_Radio_Host — 电台男主播（低沉磁性）

中年女性（阅历、淡然、安静）：
  Chinese (Mandarin)_Wise_Women — 阅历姐姐
  Chinese (Mandarin)_Soft_Girl — 柔和少女

青年（清澈、没有社会打磨感）：
  Chinese (Mandarin)_Pure-hearted_Boy — 清澈邻家弟弟
  chunzhen_xuedi — 纯真学弟
  junlang_nanyou — 俊朗男友

老年：
  Chinese (Mandarin)_Kind-hearted_Elder — 花甲奶奶
  Chinese (Mandarin)_Humorous_Elder — 搞笑大爷

【可用情绪 emotion】calm, happy, sad, angry, fearful, disgusted, surprised
【语气词标签】直接插入文本：(breath)换气, (sighs)叹气, (laughs)笑, (chuckles)轻笑, (gasps)倒吸气, (emm)犹豫
【停顿标签】<#x#>，如 <#0.5#> 停顿0.5秒
"""

SYSTEM_PROMPT = f"""你是一个专业的中文对话故事创作者，同时担任配音导演。
故事全部由"人"和"AI智能体"之间的对话记录组成，面向中国受众，具有本土特色。

{VOICE_CATALOG}

输出格式（严格 JSON，不含其他文字）：
{{
  "title": "故事标题",
  "slug": "english-kebab-slug-max-30-chars",
  "subtitle": "副标题",
  "characters": {{
    "角色名": {{
      "role": "ai|user",
      "voice_id": "从音色库中选择",
      "default_emotion": "calm|happy|sad|angry|fearful|disgusted|surprised"
    }}
  }},
  "slides": [
    {{
      "num": 1,
      "date": "2024年XX月XX日 周X XX:XX",
      "messages": [
        {{
          "role": "ai",
          "name": "助理",
          "text": "AI说的话，可包含<#0.3#>停顿和(breath)语气词",
          "emotion": "calm"
        }}
      ]
    }}
  ]
}}

创作规范：
- 共 5 张卡片，每张 3-6 轮对话（控制总时长，单条 3 句以内）
- 第1张：立局，冷静展示"外包关系"
- 第2张：日常裂缝，埋下不安细节
- 第3张：张力积累
- 第4张：转折引爆
- 第5张：留白结局，在关键决定前停住
- AI 克制、精准；人物简短、口语化
- 结尾不说教
- slug 必须是英文小写连字符，不超过 30 字符

音色与配音规范（核心要求）：
1. 每个角色必须从音色库中选最贴合的 voice_id。
2. 为每个角色设 default_emotion，反映整体基调。
3. 逐句 emotion：每条 message 单独标 emotion。同一场景下可变化。
4. 停顿控制：句间插 <#0.2#>~<#0.5#>，情绪转折前 <#0.5#>~<#0.8#>，留白处 <#1.0#>~<#2.0#>。
5. 语气词：疲惫加 (sighs)/(breath)，惊讶加 (gasps)，犹豫加 (emm)，自嘲加 (chuckles)。AI 角色克制，人类角色可丰富。
"""


async def generate_story(theme: str, tone: str, ai_style: str, characters: str) -> dict:
    """
    调用 Kimi K2.6 生成故事 JSON（含 429 重试）。
    tone: 温情向 | 悲剧向 | 留白向 | ...（自定义）
    ai_style: 陪伴感 | 工具感 | 镜子感 | ...（自定义）
    """
    prompt = f"""请创作一个对话故事：
主题：{theme}
基调：{tone}
AI形象：{ai_style}
主要角色：{characters}

直接输出 JSON。"""

    last_err = None
    for attempt in range(3):
        try:
            resp = await _client.chat.completions.create(
                model=MOONSHOT_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                max_tokens=16384,
            )
            break
        except RateLimitError as e:
            last_err = e
            wait = 2 ** attempt + 1
            await asyncio.sleep(wait)
    else:
        raise RuntimeError(f"Kimi 请求多次被限流（429），请稍后重试。最后错误：{last_err}") from last_err

    raw = resp.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        story = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Kimi 返回非合法 JSON ({e})，"
            f"finish_reason={resp.choices[0].finish_reason}"
        ) from e

    if not story.get("slug"):
        story["slug"] = re.sub(r"[^a-z0-9-]", "", story.get("title", "story").lower().replace(" ", "-")) or "story"
    return story
