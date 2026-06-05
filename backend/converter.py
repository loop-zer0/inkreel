"""Pass 2: 逐章转换 — 将小说章节转换为剧本场景"""

import json
import re
import logging
import yaml
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAI
from config import (get_llm_config, LLM_TEMPERATURE, LLM_MODE,
                    CHAPTER_SEGMENT_SIZE)
from schema import CONVERTER_SYSTEM_PROMPT
from chapter_parser import segment_long_chapter

logger = logging.getLogger(__name__)


def convert_chapter(chapter: dict, characters: list[dict], chapter_offset: int = 0) -> list[dict]:
    """将单章小说内容转换为场景列表。

    Args:
        chapter: {"number": 1, "title": "...", "content": "..."}
        characters: 已知人物表
        chapter_offset: 章节号偏移（用于分段时保持原章节号）

    Returns:
        [{"id": "SCENE_01", "source_chapter": 1, ...}, ...]
    """
    if LLM_MODE == "online" and not get_llm_config()[1]:
        logger.error("[Converter] 未配置 API Key")
        return []

    # 构建人物上下文
    if characters:
        char_ctx_lines = ["已知人物："]
        for c in characters:
            char_ctx_lines.append(f"  {c['id']}: {c['name']} ({c.get('role','')}) — {c.get('description','')}")
        char_ctx = "\n".join(char_ctx_lines)
    else:
        char_ctx = "（暂无已知人物，请从文本中识别并标记为 CHAR_01, CHAR_02 ...）"

    system_prompt = CONVERTER_SYSTEM_PROMPT.replace("{character_context}", char_ctx)

    content = chapter["content"]

    # 超长章节分段处理
    if len(content) > CHAPTER_SEGMENT_SIZE * 1.2:
        segments = segment_long_chapter(content, CHAPTER_SEGMENT_SIZE)
        all_scenes = []
        for seg_idx, seg in enumerate(segments):
            seg_chapter = {
                **chapter,
                "content": seg,
                "number": f"{chapter['number']}.{seg_idx+1}" if len(segments) > 1 else chapter["number"],
            }
            seg_scenes = _call_llm_convert(seg_chapter, system_prompt)
            all_scenes.extend(seg_scenes)
        return all_scenes

    return _call_llm_convert(chapter, system_prompt)


def _call_llm_convert(chapter: dict, system_prompt: str) -> list[dict]:
    """单次 LLM 调用：章节 → YAML → 场景列表"""
    if LLM_MODE == "online" and not get_llm_config()[1]:
        logger.error("[Converter] 未配置 API Key")
        return []

    user_msg = f"章节：{chapter['title']}\n\n{chapter['content']}"

    base_url, api_key, model = get_llm_config()
    client = OpenAI(base_url=base_url, api_key=api_key)

    try:
        resp = client.chat.completions.create(
            model=model,
            temperature=LLM_TEMPERATURE,
            max_tokens=4096,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg[:8000]},  # DeepSeek 上下文足够
            ],
        )
        raw = resp.choices[0].message.content.strip()

        # 清理 markdown 代码块
        if "```" in raw:
            parts = raw.split("```")
            # 取第一个代码块内容
            for i, p in enumerate(parts):
                if i % 2 == 1:
                    raw = p
                    if raw.startswith("yaml") or raw.startswith("yml"):
                        raw = raw.split("\n", 1)[1] if "\n" in raw else raw
                    break

        # 解析 YAML
        scenes_data = yaml.safe_load(raw)

        # 可能返回的是完整的 {scenes: [...]} 或直接是场景列表
        if isinstance(scenes_data, dict):
            scenes = scenes_data.get("scenes", [])
        elif isinstance(scenes_data, list):
            scenes = scenes_data
        else:
            logger.error(f"[Converter] YAML 格式异常: {type(scenes_data)}")
            return []

        if not isinstance(scenes, list):
            logger.error(f"[Converter] scenes 不是列表: {type(scenes)}")
            return []

        # 确保每个 scene 有 source_chapter
        for s in scenes:
            if isinstance(s, dict):
                s.setdefault("source_chapter", chapter["number"])
                if "dialogues" in s and isinstance(s["dialogues"], list):
                    for d in s["dialogues"]:
                        if isinstance(d, dict):
                            d.setdefault("emotion", "")
                            d.setdefault("action", "")

        logger.info(f"[Converter] {chapter['title']} → {len(scenes)} 个场景")
        return scenes

    except yaml.YAMLError as e:
        logger.error(f"[Converter] YAML 解析失败: {e}")
        return []
    except Exception as e:
        logger.error(f"[Converter] LLM 调用失败: {e}")
        return []


def convert_all(chapters: list[dict], characters: list[dict],
                on_progress=None) -> list[dict]:
    """并行转换所有章节（最多 3 章并行）。

    Args:
        chapters: 章节列表
        characters: 人物表
        on_progress: 回调 (current, total) 用于进度通知

    Returns:
        所有场景的合并列表（未排序，未统一 ID）
    """
    all_scenes = []
    total = len(chapters)
    completed = 0

    # 逐章串行（避免并发 API 限流，DeepSeek 免费版并发有限）
    for i, ch in enumerate(chapters):
        scenes = convert_chapter(ch, characters)
        # 给场景分配临时编号
        for s in scenes:
            s["_chapter_num"] = ch["number"]
        all_scenes.extend(scenes)
        completed += 1
        logger.info(f"[Converter] 进度: {completed}/{total} 章完成, 共 {len(all_scenes)} 个场景")
        if on_progress:
            on_progress(completed, total)

    return all_scenes
