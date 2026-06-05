"""FastAPI 服务端 — AI 小说转剧本工具

API:
  POST /api/convert    上传小说 → 处理 → 返回 YAML
  GET  /api/mode       获取当前模式 (online/offline)
  POST /api/mode       切换模式
  GET  /api/health     健康检查
"""

import os
import json
import logging
import asyncio
import time
from io import BytesIO

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from config import (HOST, PORT, MAX_FILE_SIZE_MB,
                    get_llm_config, set_llm_mode, LLM_MODE)
from chapter_parser import split_chapters, detect_chapter_format
from extractor import extract_characters
from converter import convert_all
from merger import merge
from schema import validate, dump_yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Novel2Script — AI 小说转剧本工具")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
async def index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


@app.get("/api/health")
async def health():
    base_url, api_key, model = get_llm_config()
    online_available = bool(api_key)
    return {
        "status": "ok",
        "mode": LLM_MODE,
        "model": model,
        "online_available": online_available,
    }


@app.get("/api/mode")
async def get_mode():
    base_url, api_key, model = get_llm_config()
    return {
        "mode": LLM_MODE,
        "model": model,
        "online_available": bool(api_key),
    }


@app.post("/api/mode")
async def switch_mode(req: dict):
    mode = req.get("mode", "online")
    if mode not in ("online", "offline"):
        return JSONResponse({"error": "mode 必须是 online 或 offline"}, status_code=400)
    set_llm_mode(mode)
    base_url, api_key, model = get_llm_config()
    logger.info(f"[Mode] 切换到: {mode}, 模型: {model}")
    return {"mode": LLM_MODE, "model": model}


@app.post("/api/convert")
async def convert(file: UploadFile = File(...), title: str = Form(""), author: str = Form("")):
    """上传小说文本，返回生成的剧本 YAML。

    返回 JSON:
      { "status": "ok", "yaml": "...", "meta": {...}, "warnings": [...], "errors": [...] }
    或:
      { "status": "error", "message": "..." }
    """
    # ── 校验 ──
    if not file.filename or not file.filename.endswith(('.txt', '.text', '.md')):
        return JSONResponse({"status": "error", "message": "请上传 .txt 文本文件"}, status_code=400)

    content = await file.read()
    file_size_mb = len(content) / (1024 * 1024)
    if file_size_mb > MAX_FILE_SIZE_MB:
        return JSONResponse({
            "status": "error",
            "message": f"文件过大 ({file_size_mb:.1f}MB)，限制 {MAX_FILE_SIZE_MB}MB"
        }, status_code=400)

    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = content.decode("gbk")
        except UnicodeDecodeError:
            return JSONResponse({"status": "error", "message": "文件编码不支持，请使用 UTF-8 或 GBK"}, status_code=400)

    text = text.strip()
    if len(text) < 200:
        return JSONResponse({"status": "error", "message": f"文件内容过短 ({len(text)} 字)，至少需要 200 字"}, status_code=400)

    logger.info(f"[Convert] 接收文件: {file.filename}, {len(text)} 字, {file_size_mb:.1f}MB")

    # ── 步骤 1: 章节分割 ──
    chapters = split_chapters(text)
    if len(chapters) < 3:
        fmt = detect_chapter_format(text)
        return JSONResponse({
            "status": "error",
            "message": f"检测到 {len(chapters)} 个章节，需要至少 3 章。当前章节格式: {fmt}",
            "hint": "请确保文本包含标准的章节标题（如'第一章'、'Chapter 1'）"
        }, status_code=400)

    logger.info(f"[Convert] 检测到 {len(chapters)} 章, 共 {sum(c['char_count'] for c in chapters)} 字")

    # ── 步骤 2: 人物提取 ──
    characters = await asyncio.to_thread(extract_characters, chapters)
    logger.info(f"[Convert] 人物提取完成: {len(characters)} 人")

    # ── 步骤 3: 逐章转换 ──
    all_scenes = await asyncio.to_thread(convert_all, chapters, characters)
    if not all_scenes:
        return JSONResponse({"status": "error", "message": "转换失败：未能生成任何场景"}, status_code=500)

    logger.info(f"[Convert] 转换完成: {len(all_scenes)} 个场景")

    # ── 步骤 4: 合并 ──
    script = merge(characters, all_scenes)

    # 注入用户提供的标题/作者
    if title:
        script["meta"]["title"] = title
    if author:
        script["meta"]["original_author"] = author

    # ── 步骤 5: 验证 ──
    validation_errors = validate(script)

    # ── 步骤 6: 输出 YAML ──
    yaml_str = dump_yaml(script)

    logger.info(f"[Convert] 完成! {len(script['scenes'])} 场景, {len(script['characters'])} 人物")

    return {
        "status": "ok",
        "yaml": yaml_str,
        "meta": script["meta"],
        "stats": {
            "chapters": len(chapters),
            "characters": len(script["characters"]),
            "scenes": len(script["scenes"]),
            "acts": len(script.get("acts", [])),
            "total_chars": len(text),
        },
        "warnings": [],
        "errors": validation_errors,
    }


@app.get("/api/schema")
async def get_schema_doc():
    """返回 Schema 文档（Markdown）"""
    docs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")
    doc_path = os.path.join(docs_dir, "yaml-schema.md")
    if os.path.exists(doc_path):
        with open(doc_path, "r", encoding="utf-8") as f:
            return {"content": f.read()}
    return {"content": "# Schema 文档\n\n（尚未生成）"}


@app.get("/api/download")
async def download_yaml(yaml_str: str = ""):
    """下载 YAML 文件（GET 方式，yaml_str 通过 query param 传递）"""
    # 实际下载通过前端 blob 实现，这个端点保留做服务端下载
    return JSONResponse({"status": "error", "message": "请从预览区直接下载"}, status_code=400)


if __name__ == "__main__":
    import uvicorn
    logger.info(f"Novel2Script 启动: http://{HOST}:{PORT}")
    logger.info(f"  LLM 模式: {LLM_MODE}")
    base_url, api_key, model = get_llm_config()
    logger.info(f"  模型: {model} @ {base_url}")
    uvicorn.run(app, host=HOST, port=PORT)
