"""翻译路由"""

import asyncio
import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.repositories import script as script_repo
from app.repositories import translation as trans_repo
from app.services.translator import translate_yaml

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["translations"])

# 预设语言
LANGUAGES = {
    "en": "English",
    "ja": "日本語",
    "ko": "한국어",
    "fr": "Français",
    "de": "Deutsch",
    "es": "Español",
}

# 反向：外语→中文
REVERSE_LANGUAGES = {
    "en": "English",
    "ja": "日本語",
    "ko": "한국어",
    "fr": "Français",
    "de": "Deutsch",
    "es": "Español",
    "ru": "Русский",
    "pt": "Português",
    "it": "Italiano",
}


@router.get("/scripts/{script_id}/translations")
async def list_translations(script_id: int):
    """列出剧本的所有翻译"""
    translations = trans_repo.list_by_target("script", script_id)
    script = script_repo.get_script(script_id)
    return {
        "status": "ok",
        "script_title": script.get("title", "（未命名）") if script else "（未命名）",
        "translations": translations,
    }


@router.post("/scripts/{script_id}/translate")
async def create_translation(script_id: int, req: dict):
    """翻译当前剧本"""
    script = script_repo.get_script(script_id)
    if not script:
        return JSONResponse({"status": "error", "message": "剧本不存在"}, status_code=404)

    yaml_content = script.get("yaml_content", "")
    if not yaml_content:
        return JSONResponse({"status": "error", "message": "剧本尚无 YAML 内容"}, status_code=400)

    language = req.get("language", "en")
    direction = req.get("direction", "zh2xx")

    if direction == "xx2zh":
        src_label = req.get("language_label", LANGUAGES.get(language, language))
        dst_label = "中文"
        display_label = f"{src_label}→中文"
        source_lang = src_label
        target_lang = "Chinese"
    else:
        src_label = "中文"
        dst_label = req.get("language_label", LANGUAGES.get(language, language))
        display_label = f"中文→{dst_label}"
        source_lang = "Chinese"
        target_lang = dst_label

    try:
        result = await asyncio.to_thread(translate_yaml, yaml_content, target_lang, source_lang)
    except Exception as e:
        logger.error(f"[Translation] LLM 翻译失败: {e}")
        return JSONResponse({"status": "error", "message": f"翻译失败: {e}"}, status_code=500)

    trans_id = trans_repo.create(
        target_type="script",
        target_id=script_id,
        language=language,
        language_label=display_label,
        translated_yaml=result,
    )

    return {"status": "ok", "translation_id": trans_id, "yaml": result}


@router.get("/translations/{translation_id}")
async def get_translation(translation_id: int):
    """获取翻译详情"""
    tr = trans_repo.get(translation_id)
    if not tr:
        return JSONResponse({"status": "error", "message": "翻译不存在"}, status_code=404)
    return {"status": "ok", "translation": tr}


@router.delete("/translations/{translation_id}")
async def delete_translation(translation_id: int):
    """删除翻译"""
    ok = trans_repo.delete(translation_id)
    if ok is None:
        return JSONResponse({"status": "error", "message": "翻译不存在"}, status_code=404)
    if not ok:
        return JSONResponse({"status": "error", "message": "删除失败"}, status_code=500)
    return {"status": "ok", "message": "已删除"}


@router.get("/languages")
async def list_languages():
    """可用语言列表（含双向）"""
    return {
        "status": "ok",
        "zh2xx": LANGUAGES,       # 中译外
        "xx2zh": REVERSE_LANGUAGES,  # 外译中
    }
