"""YAML Schema 定义与验证

剧本 YAML 结构：
  meta        — 元信息（标题、作者、类型等）
  characters  — 人物表
  scenes      — 场景列表（核心）
  acts        — 分幕结构（可选）
"""

import yaml
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# ── Schema 版本 ──
SCHEMA_VERSION = "1.0"

# ── YAML 模板（用于 LLM 输出引导）──
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

# ── LLM System Prompt（用于逐章转换）──
CONVERTER_SYSTEM_PROMPT = """你是一位专业的影视编剧，擅长将小说改编为剧本。请将以下小说章节转换为剧本 YAML。

规则：
1. 识别所有场景（地点变化 = 新场景），提取场景的时间、地点、氛围
2. 将叙述性文字中的对话提取为标准台词格式（speaker + line + action + emotion）
3. 叙述性文字中没有直接对话的内容，归纳为场景的 summary
4. characters_present 用已有的人物 ID（如 CHAR_01），新人物留空名字让系统后续补充
5. 保持原著的叙事节奏，不要遗漏重要情节
6. 只输出 YAML，不要输出解释文字

{character_context}"""

# ── LLM System Prompt（用于人物提取）──
EXTRACTOR_SYSTEM_PROMPT = """你是一位专业的剧本分析师。请从以下小说片段中提取所有人物信息。

对每个人物，提取：
- name: 姓名
- role: 主角/配角/反派/龙套
- gender: 男/女
- description: 一句话描述（外貌、性格、身份）

输出 JSON 数组：
[{"name": "张三", "role": "主角", "gender": "男", "description": "..."}, ...]

只输出 JSON，不要其他文字。"""


def validate(script: dict) -> list[str]:
    """验证生成的剧本结构完整性，返回错误列表"""
    errors = []

    if "meta" not in script:
        errors.append("缺少 meta 元信息")
    else:
        meta = script["meta"]
        if not meta.get("title"):
            errors.append("meta.title 缺失")

    if "characters" not in script:
        errors.append("缺少 characters 人物表")
    elif not isinstance(script["characters"], list):
        errors.append("characters 必须是列表")
    else:
        char_ids = set()
        for i, c in enumerate(script["characters"]):
            cid = c.get("id", f"CHAR_{i+1:02d}")
            if cid in char_ids:
                errors.append(f"人物 ID 重复: {cid}")
            char_ids.add(cid)
            if not c.get("name"):
                errors.append(f"{cid} 缺少 name")

    if "scenes" not in script:
        errors.append("缺少 scenes 场景列表")
    elif not isinstance(script["scenes"], list):
        errors.append("scenes 必须是列表")
    else:
        all_char_ids = {c.get("id") for c in script.get("characters", [])}
        scene_ids = set()
        for i, s in enumerate(script["scenes"]):
            sid = s.get("id", f"SCENE_{i+1:02d}")
            if sid in scene_ids:
                errors.append(f"场景 ID 重复: {sid}")
            scene_ids.add(sid)
            if not s.get("summary") and not s.get("dialogues"):
                errors.append(f"{sid} 既无 summary 也无 dialogues")
            for j, d in enumerate(s.get("dialogues", [])):
                if not d.get("line"):
                    errors.append(f"{sid} dialogue[{j}] 缺少 line")
                if d.get("speaker") and d["speaker"] not in all_char_ids and d["speaker"] not in char_ids:
                    pass  # 新出场人物，不报错

    return errors


def dump_yaml(script: dict) -> str:
    """将剧本 dict 序列化为格式化的 YAML 字符串"""
    # 添加元信息
    script.setdefault("meta", {})
    script["meta"]["generated_at"] = datetime.now().isoformat(timespec="seconds")
    script["meta"]["schema_version"] = SCHEMA_VERSION

    # 自定义 YAML dumper，保留中文可读性
    class ScriptDumper(yaml.Dumper):
        pass

    def str_representer(dumper, data):
        if '\n' in data or len(data) > 80:
            return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
        return dumper.represent_scalar('tag:yaml.org,2002:str', data)

    ScriptDumper.add_representer(str, str_representer)

    return yaml.dump(script, Dumper=ScriptDumper, allow_unicode=True,
                     default_flow_style=False, sort_keys=False, width=120)
