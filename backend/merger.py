"""Pass 3: 合并去重 — 统一 ID、去重人物、排序场景、推断分幕"""

import re
import logging

logger = logging.getLogger(__name__)


def merge(characters: list[dict], all_scenes: list[dict]) -> dict:
    """合并所有处理结果，生成最终剧本 dict。

    Args:
        characters: extractor 提取的人物表（已有 CHAR_01..ID）
        all_scenes: converter 输出的所有场景列表

    Returns:
        完整剧本 dict（meta + characters + scenes + acts）
    """
    # ── 1. 人物去重 & ID 统一 ──
    merged_characters = _deduplicate_characters(characters, all_scenes)

    # ── 2. 场景排序 & ID 重编号 ──
    # 按源章节号排序，同一章内保持原始顺序
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

    # 更新 transitions_to 中的场景 ID 引用
    for s in all_scenes:
        old_trans = s.get("transitions_to")
        if old_trans and old_trans in scene_id_map:
            s["transitions_to"] = scene_id_map[old_trans]
        elif old_trans:
            s["transitions_to"] = _guess_next_scene(s["id"], all_scenes)

    # 补全 transitions_to（没有显式指定的，自动指向下一个）
    for i, s in enumerate(all_scenes):
        if not s.get("transitions_to") and i + 1 < len(all_scenes):
            s["transitions_to"] = all_scenes[i + 1]["id"]

    # ── 3. 构建 meta ──
    chapter_nums = sorted(set(
        s.get("source_chapter", 0) for s in all_scenes
    ))
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

    # ── 4. 推断分幕结构（三幕或四幕）──
    acts = _infer_acts(all_scenes)

    # ── 5. 组装最终结果 ──
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


def _deduplicate_characters(characters: list[dict], scenes: list[dict]) -> list[dict]:
    """人物去重：按名字归一化，同名人合并"""
    # 简单策略：按 name 去重
    seen = {}
    for c in characters:
        name = c.get("name", "").strip()
        if not name:
            continue
        if name in seen:
            # 合并 description
            existing = seen[name]
            if c.get("description") and c["description"] not in existing.get("description", ""):
                existing["description"] = existing.get("description", "") + "；" + c["description"]
        else:
            seen[name] = dict(c)

    # 重新编号
    result = []
    for i, (name, c) in enumerate(seen.items()):
        old_id = c.get("id", "")
        new_id = f"CHAR_{i+1:02d}"
        c["id"] = new_id
        result.append(c)

        # 更新场景中引用此人物 ID 的地方
        for s in scenes:
            if old_id and old_id in (s.get("characters_present") or []):
                s["characters_present"] = [new_id if x == old_id else x for x in s["characters_present"]]
            for d in s.get("dialogues", []):
                if d.get("speaker") == old_id:
                    d["speaker"] = new_id

    return result


def _infer_acts(scenes: list[dict]) -> list[dict]:
    """根据场景数量自动推断分幕结构"""
    n = len(scenes)
    if n < 4:
        return [{"act": 1, "title": "全剧", "scenes": [s["id"] for s in scenes]}]

    # 四幕结构（适合大多数故事）
    boundaries = [0,
                  max(1, n // 4),
                  max(2, n // 2),
                  max(3, 3 * n // 4),
                  n]

    return [
        {"act": 1, "title": "开端 / 建置",   "scenes": [s["id"] for s in scenes[boundaries[0]:boundaries[1]]]},
        {"act": 2, "title": "发展 / 对抗",   "scenes": [s["id"] for s in scenes[boundaries[1]:boundaries[2]]]},
        {"act": 3, "title": "高潮 / 转折",   "scenes": [s["id"] for s in scenes[boundaries[2]:boundaries[3]]]},
        {"act": 4, "title": "结局 / 收束",   "scenes": [s["id"] for s in scenes[boundaries[3]:boundaries[4]]]},
    ]


def _guess_next_scene(current_id: str, scenes: list[dict]) -> str:
    """根据编号猜测下一个场景 ID"""
    m = re.match(r'SCENE_(\d+)', current_id)
    if m:
        n = int(m.group(1))
        return f"SCENE_{n+1:02d}"
    return ""
