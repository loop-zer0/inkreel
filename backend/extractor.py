"""Pass 1: 人物提取 — 扫描全文识别所有人物"""

import json
import logging
from openai import OpenAI
from config import get_llm_config, LLM_TEMPERATURE, LLM_MODE
from schema import EXTRACTOR_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


def extract_characters(chapters: list[dict]) -> list[dict]:
    """从所有章节中提取人物表。

    策略：取每章前 500 字 + 后 200 字拼接，发送给 LLM 一次性提取。
    超多章节时取前 3 章 + 后 1 章。
    """
    base_url, api_key, model = get_llm_config()
    if LLM_MODE == "online" and not api_key:
        logger.warning("未配置 API Key，使用空人物表")
        return []

    # 拼接采样文本
    if len(chapters) <= 4:
        selected = chapters
    else:
        selected = chapters[:3] + chapters[-1:]

    snippets = []
    for ch in selected:
        content = ch["content"]
        head = content[:500]
        tail = content[-200:] if len(content) > 500 else ""
        snippets.append(f"【{ch['title']}】\n{head}\n...\n{tail}")

    sample_text = "\n\n".join(snippets)
    # 限制总长度
    if len(sample_text) > 6000:
        sample_text = sample_text[:6000]

    logger.info(f"[Extractor] 采样文本 {len(sample_text)} 字，来自 {len(selected)} 章")

    client = OpenAI(base_url=base_url, api_key=api_key)

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

        return characters

    except json.JSONDecodeError as e:
        logger.error(f"[Extractor] JSON 解析失败: {e}\n原始输出: {raw[:300]}")
        return []
    except Exception as e:
        logger.error(f"[Extractor] LLM 调用失败: {e}")
        return []
