"""系统路由 — 健康检查、模式切换、Schema 文档、文件下载"""

import os
import logging

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse

from app.config import (get_llm_config, set_llm_mode, LLM_MODE,
                        FRONTEND_DIR, DOCS_DIR, OUTPUT_DIR)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
async def health():
    _base_url, api_key, model = get_llm_config()
    return {
        "status": "ok",
        "mode": LLM_MODE,
        "model": model,
        "online_available": bool(api_key),
    }


@router.get("/mode")
async def get_mode():
    _base_url, api_key, model = get_llm_config()
    return {
        "mode": LLM_MODE,
        "model": model,
        "online_available": bool(api_key),
    }


@router.post("/mode")
async def switch_mode(req: dict):
    mode = req.get("mode", "online")
    if mode not in ("online", "offline"):
        return JSONResponse({"error": "mode 必须是 online 或 offline"}, status_code=400)
    set_llm_mode(mode)
    _base_url, _api_key, model = get_llm_config()
    logger.info(f"[Mode] 切换到: {mode}, 模型: {model}")
    return {"mode": LLM_MODE, "model": model}


@router.get("/schema")
async def get_schema_doc():
    doc_path = os.path.join(DOCS_DIR, "yaml-schema.md")
    if os.path.exists(doc_path):
        with open(doc_path, "r", encoding="utf-8") as f:
            return {"content": f.read()}
    return {"content": "# Schema 文档\n\n（尚未生成）"}


@router.get("/download/{filename}")
async def download_yaml(filename: str):
    file_path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(file_path):
        return JSONResponse({"status": "error", "message": "文件不存在"}, status_code=404)
    return FileResponse(file_path, media_type="text/yaml", filename=filename)
