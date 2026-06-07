"""系统路由 — 健康检查、Schema 文档、文件下载"""

import os
import logging

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse

from app.config import get_llm_config, FRONTEND_DIR, DOCS_DIR, OUTPUT_DIR

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
async def health():
    _base_url, api_key, model = get_llm_config()
    return {
        "status": "ok",
        "model": model,
        "online_available": bool(api_key),
    }


@router.get("/schema")
async def get_schema_doc():
    doc_path = os.path.join(DOCS_DIR, "yaml-schema.md")
    if os.path.exists(doc_path):
        with open(doc_path, "r", encoding="utf-8") as f:
            return {"content": f.read()}
    return {"content": "# Schema 文档\n\n（尚未生成）"}


@router.get("/download/{filename}")
async def download_yaml(filename: str):
    file_path = os.path.realpath(os.path.join(OUTPUT_DIR, filename))
    expected_dir = os.path.realpath(OUTPUT_DIR)
    if not file_path.startswith(expected_dir + os.sep) and file_path != expected_dir:
        return JSONResponse({"status": "error", "message": "非法的文件路径"}, status_code=400)
    if not os.path.isfile(file_path):
        return JSONResponse({"status": "error", "message": "文件不存在"}, status_code=404)
    return FileResponse(file_path, media_type="text/yaml", filename=filename)
