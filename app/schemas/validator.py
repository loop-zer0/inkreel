"""YAML Schema 定义 — 验证 + 序列化"""

import yaml
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "1.0"


def validate(script: dict) -> list[str]:
    """验证剧本结构完整性，返回错误列表"""
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

    return errors


def dump_yaml(script: dict) -> str:
    """将剧本 dict 序列化为格式化的 YAML 字符串"""
    script.setdefault("meta", {})
    script["meta"]["generated_at"] = datetime.now().isoformat(timespec="seconds")
    script["meta"]["schema_version"] = SCHEMA_VERSION

    class ScriptDumper(yaml.Dumper):
        pass

    def str_representer(dumper, data):
        if '\n' in data or len(data) > 80:
            return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
        return dumper.represent_scalar('tag:yaml.org,2002:str', data)

    ScriptDumper.add_representer(str, str_representer)

    return yaml.dump(script, Dumper=ScriptDumper, allow_unicode=True,
                     default_flow_style=False, sort_keys=False, width=120)
