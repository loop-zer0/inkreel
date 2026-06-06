"""Pass 1: 人物提取 — 扫描全文识别所有人物"""

import json
import logging
from typing import List, Optional
from app.config import LLM_TEMPERATURE, LLM_MODE
from app.schemas.prompts import EXTRACTOR_SYSTEM_PROMPT
from app.services.llm import get_client, get_model

logger = logging.getLogger(__name__)


def extract_characters(chapters: List[dict], novel_id: int = None) -> List[dict]:
    """从章节列表中提取人物表。提供 novel_id 时优先读缓存。"""
    # 缓存读取
    if novel_id:
        cached = _load_cached_characters(novel_id)
        if cached:
            logger.info(f"[Extractor] 从缓存加载 {len(cached)} 个人物（novel_id={novel_id}）")
            return cached

    if LLM_MODE == "online" and not _has_api_key():
        logger.warning("未配置 API Key，使用空人物表")
        return []

    # 采样拼接
    selected = chapters[:3] + chapters[-1:] if len(chapters) > 4 else chapters

    snippets = []
    for ch in selected:
        content = ch["content"]
        head = content[:500]
        tail = content[-200:] if len(content) > 500 else ""
        snippets.append(f"【{ch['title']}】\n{head}\n...\n{tail}")

    sample_text = "\n\n".join(snippets)
    if len(sample_text) > 6000:
        sample_text = sample_text[:6000]

    logger.info(f"[Extractor] 采样文本 {len(sample_text)} 字，来自 {len(selected)} 章")

    client = get_client()
    model = get_model()

    try:
        resp = client.chat.completions.create(
            model=model,
            temperature=LLM_TEMPERATURE,
            messages=[
                {"role": "system", "content": EXTRACTOR_SYSTEM_PROMPT},
                {"role": "user", "content": sample_text},
            ],
        )
        raw = resp.choices[0].message.content.strip()

        # 清理 markdown 代码块
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        characters = json.loads(raw)
        logger.info(f"[Extractor] 提取到 {len(characters)} 个人物")

        # 分配 ID
        for i, c in enumerate(characters):
            c["id"] = f"CHAR_{i+1:02d}"
            c.setdefault("role", "配角")
            c.setdefault("gender", "未知")
            c.setdefault("relations", [])

        # 缓存
        if novel_id:
            _save_cached_characters(novel_id, characters)

        return characters

    except json.JSONDecodeError as e:
        logger.error(f"[Extractor] JSON 解析失败: {e}\n原始输出: {raw[:300] if 'raw' in dir() else 'N/A'}")
        return []
    except Exception as e:
        logger.error(f"[Extractor] LLM 调用失败: {e}")
        return []


def _has_api_key() -> bool:
    from app.config import get_llm_config
    return bool(get_llm_config()[1])


def _load_cached_characters(novel_id: int) -> Optional[List[dict]]:
    try:
        from app.repositories.context import get_chapter_context
        ctx = get_chapter_context(novel_id, 0)
        if ctx and ctx.get("characters_intro"):
            return json.loads(ctx["characters_intro"])
    except Exception as e:
        logger.warning(f"[Extractor] 读取人物缓存失败: {e}")
    return None


def _save_cached_characters(novel_id: int, characters: List[dict]):
    try:
        from app.repositories.context import save_chapter_context
        save_chapter_context(
            novel_id=novel_id,
            chapter_number=0,
            summary="[人物表缓存]",
            key_events="",
            characters_intro=json.dumps(characters, ensure_ascii=False),
        )
        logger.info(f"[Extractor] 人物表已缓存（novel_id={novel_id}）")
    except Exception as e:
        logger.warning(f"[Extractor] 保存人物缓存失败: {e}")
