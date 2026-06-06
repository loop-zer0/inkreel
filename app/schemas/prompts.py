"""YAML Schema 定义 — LLM Prompt 模板"""

# YAML 模板（用于 LLM 输出引导）
SCHEMA_TEMPLATE = """```yaml
meta:
  title: "作品名"
  original_author: "原作者"
  source_chapters: [1, 2, 3]
  genre: "类型"
  total_scenes: 0

characters:
  - id: CHAR_01
    name: "姓名"
    role: 主角/配角/反派
    gender: 男/女
    description: "简要描述"

scenes:
  - id: SCENE_01
    source_chapter: 1
    location: "地点"
    time: "时间"
    characters_present: [CHAR_01]
    atmosphere: "氛围"
    summary: "场景概要"
    dialogues:
      - speaker: CHAR_01
        line: "台词"
        action: "动作描述"
        emotion: 情绪
    transitions_to: SCENE_02
```"""

# 人物提取 System Prompt
EXTRACTOR_SYSTEM_PROMPT = """你是一位专业的剧本分析师。请从以下小说片段中提取所有人物信息。

对每个人物，提取：
- name: 姓名
- role: 主角/配角/反派/龙套
- gender: 男/女
- description: 一句话描述（外貌、性格、身份）

输出 JSON 数组：
[{"name": "张三", "role": "主角", "gender": "男", "description": "..."}, ...]

只输出 JSON，不要其他文字。"""

# 逐章转换 System Prompt（基础版，无上下文）
CONVERTER_SYSTEM_PROMPT = """你是一位专业的影视编剧，擅长将小说改编为剧本。请将以下小说章节转换为剧本 YAML。

规则：
1. 识别所有场景（地点变化 = 新场景），提取场景的时间、地点、氛围
2. 将叙述性文字中的对话提取为标准台词格式（speaker + line + action + emotion）
3. 叙述性文字中没有直接对话的内容，归纳为场景的 summary
4. characters_present 用已有的人物 ID（如 CHAR_01），新人物留空名字让系统后续补充
5. 保持原著的叙事节奏，不要遗漏重要情节
6. 只输出 YAML，不要输出解释文字

{character_context}"""

# 逐章转换 System Prompt（带上下文）
CONTEXT_CONVERTER_PROMPT = """你是一位专业的影视编剧，擅长将小说改编为剧本。请将以下小说章节转换为剧本 YAML。

{context_section}

规则：
1. 识别所有场景（地点变化 = 新场景），提取场景的时间、地点、氛围
2. 将叙述性文字中的对话提取为标准台词格式
3. 保持原著的叙事节奏，不要遗漏重要情节
4. **必须使用以下英文键名，不能使用中文键名**

{character_context}

**强制输出格式（严格遵循，键名不可修改）：**
```yaml
scenes:
  - id: SCENE_01
    source_chapter: {chapter_num}
    location: "地点"
    time: "时间"
    characters_present: [CHAR_01, CHAR_02]
    atmosphere: "氛围"
    summary: "场景概要"
    dialogues:
      - speaker: CHAR_01
        line: "台词内容"
        action: "动作描述"
        emotion: 情绪

chapter_summary: "用一句话概括本章核心剧情"
```"""
