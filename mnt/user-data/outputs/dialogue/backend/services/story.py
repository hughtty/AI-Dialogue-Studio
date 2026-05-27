"""
services/story.py — 调用 Claude API 生成对话故事 JSON
"""
import json
import anthropic
from ..core.config import CLAUDE_API_KEY

client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)

SYSTEM_PROMPT = """你是一个专业的中文对话故事创作者。
你创作的故事全部由"人"和"AI智能体"之间的对话记录组成，面向中国受众，具有本土特色。

输出格式要求：
- 严格输出 JSON，不含任何其他文字
- 结构如下：
{
  "title": "故事标题",
  "subtitle": "副标题（如：所有对话记录均来自「助理」应用）",
  "slides": [
    {
      "num": 1,
      "date": "2024年XX月XX日 周X XX:XX",
      "messages": [
        {"role": "ai", "name": "助理", "text": "AI说的话"},
        {"role": "user", "name": "角色姓名", "text": "人说的话"}
      ]
    }
  ]
}

创作规范：
- 共 5 张卡片，每张 3-8 轮对话
- 第1张：立局，冷静展示"外包关系"
- 第2张：日常裂缝，埋下一个让读者不安的细节
- 第3张：张力积累，矛盾升温但未爆发
- 第4张：转折引爆，一句话打破平衡
- 第5张：留白结局，在关键决定前停住
- AI的话克制、精准，不超过3句
- 人物的话简短、口语化，可以用省略号
- 故事结尾不说教，留给读者自己感受"""


async def generate_story(theme: str, tone: str, ai_style: str, characters: str) -> dict:
    """
    调用 Claude 生成故事 JSON。
    tone: 温情向 | 悲剧向 | 留白向
    ai_style: 工具感 | 陪伴感 | 镜子感
    """
    prompt = f"""请创作一个对话故事，要求如下：
主题：{theme}
基调：{tone}
AI形象：{ai_style}
主要角色：{characters}

请直接输出 JSON，不要有任何其他文字。"""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
        system=SYSTEM_PROMPT,
    )

    raw = message.content[0].text.strip()
    # 移除可能的 markdown 代码块
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    return json.loads(raw)
