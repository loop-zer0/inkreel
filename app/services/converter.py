"""Pass 2: 逐章转换 — 将小说章节转换为剧本场景

合并了 convert_chapter 和 convert_chapter_with_context 两个函数，
统一为带可选上下文的单一入口。
"""

import logging
import yaml
from typing import List, Tuple
from app.config import (LLM_TEMPERATURE, LLM_MODE, LLM_MAX_TOKENS,
                        CHAPTER_SEGMENT_SIZE)
from app.schemas.prompts import CONVERTER_SYSTEM_PROMPT, CONTEXT_CONVERTER_PROMPT
from app.services.llm import get_client, get_model
from app.utils.parser import segment_long_chapter

logger = logging.getLogger(__name__)

# ── 中文键名 → 英文键名映射 ──
_SCENE_KEY_MAP = {
    "章节": "source_chapter", "章节编号": "source_chapter",
    "时间": "time", "地点": "location", "位置": "location",
    "氛围": "atmosphere", "气氛": "atmosphere",
    "场景概要": "summary", "概要": "summary", "摘要": "summary",
    "出场人物": "characters_present", "角色": "characters_present", "人物": "characters_present",
    "对话": "dialogues", "台词": "dialogues",
    "场景": "id", "转场到": "transitions_to",
}
_DIALOGUE_KEY_MAP = {
    "角色": "speaker", "说话人": "speaker", "人物": "speaker",
    "台词": "line", "对白": "line", "对话": "line",
    "动作": "action", "动作描述": "action", "表演": "action",
    "情绪": "emotion", "情感": "emotion",
    "潜台词": "subtext",
}


def _normalize_scene_keys(s: dict):
    for cn_key, en_key in _SCENE_KEY_MAP.items():
        if cn_key in s and en_key not in s:
            s[en_key] = s.pop(cn_key)


def _normalize_dialogue_keys(d: dict):
    for cn_key, en_key in _DIALOGUE_KEY_MAP.items():
        if cn_key in d and en_key not in d:
            d[en_key] = d.pop(cn_key)


def _make_character_context(characters: List[dict]) -> str:
    """构建人物表上下文"""
    if not characters:
        return "（暂无已知人物，请从文本中识别并标记为 CHAR_01, CHAR_02 ...）"
    lines = ["已知人物："]
    for c in characters:
        lines.append(f"  {c['id']}: {c['name']} ({c.get('role', '')}) — {c.get('description', '')}")
    return "\n".join(lines)


def convert_chapter(chapter: dict, characters: List[dict],
                    novel_id: int = None, script_id: int = None,
                    context_text: str = "") -> Tuple[List[dict], str]:
    """将单章小说转换为场景列表（统一入口，支持可选上下文）

    Args:
        chapter: {"number": 1, "title": "...", "content": "..."}
        characters: 已知人物表
        novel_id: 小说 ID（用于上下文缓存）
        script_id: 剧本 ID
        context_text: 预构建的上下文文本（为空则自动构建）

    Returns:
        (scenes_list, chapter_summary)
    """
    if LLM_MODE == "online" and not _has_api_key():
        logger.error("[Converter] 未配置 API Key")
        return [], ""

    char_ctx = _make_character_context(characters)

    # 构建 System Prompt
    if context_text:
        context_section = f"【上下文信息】\n{context_text}"
        system_prompt = CONTEXT_CONVERTER_PROMPT.format(
            context_section=context_section,
            character_context=char_ctx,
            chapter_num=chapter["number"],
        )
    else:
        system_prompt = CONVERTER_SYSTEM_PROMPT.replace("{character_context}", char_ctx)

    content = chapter["content"]

    # 超长章节分段
    if len(content) > CHAPTER_SEGMENT_SIZE * 1.2:
        segments = segment_long_chapter(content, CHAPTER_SEGMENT_SIZE)
        all_scenes = []
        summaries = []
        for seg_idx, seg in enumerate(segments):
            seg_ch = {**chapter, "content": seg}
            if len(segments) > 1:
                seg_ch["number"] = f"{chapter['number']}.{seg_idx + 1}"
            scenes, summary = _call_llm(seg_ch, system_prompt, chapter["number"])
            all_scenes.extend(scenes)
            if summary:
                summaries.append(summary)
        return all_scenes, "；".join(summaries)

    return _call_llm(chapter, system_prompt, chapter["number"])


def convert_all(chapters: List[dict], characters: List[dict]) -> List[dict]:
    """串行转换所有章节（避免 API 限流）"""
    all_scenes = []
    for i, ch in enumerate(chapters):
        scenes, _summary = convert_chapter(ch, characters)
        for s in scenes:
            s["_chapter_num"] = ch["number"]
        all_scenes.extend(scenes)
        logger.info(f"[Converter] 进度: {i + 1}/{len(chapters)} 章完成, 共 {len(all_scenes)} 场景")
    return all_scenes


def build_chapter_context(novel_id: int, chapter_number: float,
                          characters: List[dict]) -> str:
    """构建单章转换的上下文文本"""
    from app.repositories.context import get_all_generated_summaries

    parts = []

    summaries = get_all_generated_summaries(novel_id, chapter_number)
    if summaries:
        parts.append(summaries)

    parts.append(_make_character_context(characters))
    return "\n\n".join(parts)


# ── 内部实现 ──

def _has_api_key() -> bool:
    from app.config import get_llm_config
    return bool(get_llm_config()[1])


def _call_llm(chapter: dict, system_prompt: str,
              original_chapter_num: float) -> Tuple[List[dict], str]:
    """单次 LLM 调用：章节 → YAML → (场景列表, 摘要)"""
    user_msg = f"章节：{chapter['title']}\n\n{chapter['content']}"

    client = get_client()
    model = get_model()

    try:
        resp = client.chat.completions.create(
            model=model,
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg[:8000]},
            ],
        )
        raw = (resp.choices[0].message.content or "").strip()
        if not raw:
            logger.error("[Converter] LLM 返回空内容")
            return [], ""
    except Exception as e:
        logger.error(f"[Converter] LLM 调用失败: {e}")
        return [], ""

    # 提取 YAML
    yaml_text = _extract_yaml(raw)
    if not yaml_text:
        return [], ""

    # 解析
    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError as e:
        logger.error(f"[Converter] YAML 解析失败: {e}\n{yaml_text[:300]}")
        return [], ""

    chapter_summary = ""
    scenes = []

    if isinstance(data, dict):
        scenes = data.get("scenes", [])
        chapter_summary = data.get("chapter_summary", "") or data.get("summary", "")
        if not scenes and "location" in data:
            scenes = [data]
    elif isinstance(data, list):
        scenes = data
    elif data is None:
        logger.error(f"[Converter] YAML 为 None\n{yaml_text[:300]}")
        return [], ""

    if not isinstance(scenes, list):
        logger.error(f"[Converter] scenes 不是列表: {type(scenes)}")
        return [], chapter_summary

    # 后处理
    for s in scenes:
        if isinstance(s, dict):
            _normalize_scene_keys(s)
            s.setdefault("source_chapter", original_chapter_num)
            for d in s.get("dialogues", []) or []:
                if isinstance(d, dict):
                    _normalize_dialogue_keys(d)
                    d.setdefault("emotion", "")
                    d.setdefault("action", "")

    logger.info(
        f"[Converter] {chapter['title']} → {len(scenes)} 场景"
        + (f", 摘要: {chapter_summary[:40]}..." if chapter_summary else "")
    )
    return scenes, chapter_summary


def _extract_yaml(raw: str) -> str:
    """从 LLM 原始输出中提取 YAML 文本"""
    yaml_text = raw
    if "```" in raw:
        parts = raw.split("```")
        code_blocks = [p for i, p in enumerate(parts) if i % 2 == 1 and p.strip()]
        if code_blocks:
            yaml_text = code_blocks[0]
            first_line = yaml_text.split("\n")[0].strip()
            if first_line in ("yaml", "yml"):
                yaml_text = yaml_text.split("\n", 1)[1] if "\n" in yaml_text else yaml_text
    elif "scenes:" in raw:
        idx = raw.find("scenes:")
        if idx > 0:
            yaml_text = raw[idx:]

    return yaml_text.strip()
