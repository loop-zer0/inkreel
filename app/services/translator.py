"""LLM 翻译服务 — 用 Mimo 翻译 YAML 剧本内容，支持中↔外双向"""

import logging
from app.services.llm import get_client, get_model

logger = logging.getLogger(__name__)

TRANSLATE_SYSTEM_PROMPT = """You are a professional literary translator. Translate the following YAML script content from {source_language} to {target_language}.

CRITICAL RULES:
1. Keep ALL YAML structure exactly as-is — keys, indentation, list markers, all unchanged
2. Only translate the VALUES: dialogue text, descriptions, narration, atmosphere, summary
3. Do NOT translate: character IDs (CHAR_01 etc.), scene IDs (SCENE_01 etc.), chapter numbers, act titles
4. Preserve all special YAML syntax: | for multi-line, quotes, anchors
5. Translate naturally for the target language, preserving the literary tone

Output ONLY the translated YAML, no markdown fences, no explanations."""


def translate_yaml(yaml_content: str, target_language: str = "English",
                   source_language: str = "Chinese") -> str:
    """双向翻译剧本 YAML，返回译文 YAML 字符串"""
    if not yaml_content.strip():
        return ""

    client = get_client()
    model = get_model()

    prompt = TRANSLATE_SYSTEM_PROMPT.format(
        source_language=source_language,
        target_language=target_language,
    )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": yaml_content},
            ],
            temperature=0.2,
            max_tokens=8192,
        )
        result = response.choices[0].message.content or ""
        # 清理可能的 markdown fences
        result = result.strip()
        if result.startswith("```"):
            lines = result.split("\n")
            result = "\n".join(lines[1:]) if len(lines) > 1 else result
            if result.endswith("```"):
                result = result[:-3].strip()
        return result
    except Exception as e:
        logger.error(f"[Translator] 翻译失败: {e}")
        raise
