"""Pass 3: 合并去重 — 统一 ID、去重人物、排序场景、推断分幕"""

import re
import logging
from typing import List

logger = logging.getLogger(__name__)


def merge(characters: List[dict], all_scenes: List[dict]) -> dict:
    """合并所有处理结果，生成最终剧本 dict"""
    # 1. 人物去重 & ID 统一
    merged_characters = _deduplicate_characters(characters, all_scenes)

    # 2. 场景排序
    def sort_key(s):
        cn = s.get("source_chapter", 0)
        if isinstance(cn, str):
            try:
                cn = float(cn)
            except ValueError:
                cn = 0
        return cn

    all_scenes.sort(key=sort_key)

    # 重编号场景 ID
    scene_id_map = {}
    for i, s in enumerate(all_scenes):
        old_id = s.get("id", f"SCENE_{i+1:02d}")
        new_id = f"SCENE_{i+1:02d}"
        scene_id_map[old_id] = new_id
        s["id"] = new_id

    # 更新 transitions_to
    for s in all_scenes:
        old_trans = s.get("transitions_to")
        if old_trans and old_trans in scene_id_map:
            s["transitions_to"] = scene_id_map[old_trans]
        elif old_trans:
            s["transitions_to"] = _guess_next_scene(s["id"], all_scenes)

    # 补全空 transitions_to
    for i, s in enumerate(all_scenes):
        if not s.get("transitions_to") and i + 1 < len(all_scenes):
            s["transitions_to"] = all_scenes[i + 1]["id"]

    # 3. 构建 meta
    raw_nums = set()
    for s in all_scenes:
        cn = s.get("source_chapter", 0)
        raw_nums.add(str(cn))

    def _sort_key(x):
        try:
            return float(x)
        except ValueError:
            return 0.0

    chapter_nums = sorted(raw_nums, key=_sort_key)
    source_chapters = []
    for cn in chapter_nums:
        try:
            source_chapters.append(int(cn))
        except (ValueError, TypeError):
            source_chapters.append(cn)

    meta = {
        "title": "（未命名）",
        "original_author": "（未知）",
        "adapter": "AI 辅助改编",
        "source_chapters": source_chapters,
        "total_scenes": len(all_scenes),
    }

    # 4. 推断分幕
    acts = _infer_acts(all_scenes)

    # 5. 组装
    script = {
        "meta": meta,
        "characters": merged_characters,
        "scenes": all_scenes,
        "acts": acts,
    }

    # 清理内部字段
    for s in all_scenes:
        s.pop("_chapter_num", None)

    logger.info(f"[Merger] 最终: {len(merged_characters)} 人, {len(all_scenes)} 场景, {len(acts)} 幕")
    return script


def _deduplicate_characters(characters: List[dict], scenes: List[dict]) -> List[dict]:
    """按名字去重，合并描述，重编号 ID"""
    seen = {}
    for c in characters:
        name = c.get("name", "").strip()
        if not name:
            continue
        if name in seen:
            existing = seen[name]
            if c.get("description") and c["description"] not in existing.get("description", ""):
                existing["description"] = existing.get("description", "") + "；" + c["description"]
        else:
            seen[name] = dict(c)

    result = []
    for i, (name, c) in enumerate(seen.items()):
        old_id = c.get("id", "")
        new_id = f"CHAR_{i+1:02d}"
        c["id"] = new_id
        result.append(c)

        # 更新场景中的人物 ID 引用
        for s in scenes:
            if old_id and old_id in (s.get("characters_present") or []):
                s["characters_present"] = [new_id if x == old_id else x for x in s["characters_present"]]
            for d in s.get("dialogues", []):
                if d.get("speaker") == old_id:
                    d["speaker"] = new_id

    return result


def _infer_acts(scenes: List[dict]) -> List[dict]:
    """根据场景数量推断分幕结构"""
    n = len(scenes)
    if n < 4:
        return [{"act": 1, "title": "全剧", "scenes": [s["id"] for s in scenes]}]

    boundaries = [0,
                  max(1, n // 4),
                  max(2, n // 2),
                  max(3, 3 * n // 4),
                  n]

    return [
        {"act": 1, "title": "开端 / 建置", "scenes": [s["id"] for s in scenes[boundaries[0]:boundaries[1]]]},
        {"act": 2, "title": "发展 / 对抗", "scenes": [s["id"] for s in scenes[boundaries[1]:boundaries[2]]]},
        {"act": 3, "title": "高潮 / 转折", "scenes": [s["id"] for s in scenes[boundaries[2]:boundaries[3]]]},
        {"act": 4, "title": "结局 / 收束", "scenes": [s["id"] for s in scenes[boundaries[3]:boundaries[4]]]},
    ]


def _guess_next_scene(current_id: str, scenes: List[dict]) -> str:
    m = re.match(r'SCENE_(\d+)', current_id)
    if m:
        n = int(m.group(1))
        return f"SCENE_{n+1:02d}"
    return ""
