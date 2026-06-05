"""FastAPI 服务端 — AI 小说转剧本工具

API:
  POST /api/convert    上传小说 → 处理 → 返回 YAML
  GET  /api/mode       获取当前模式 (online/offline)
  POST /api/mode       切换模式
  GET  /api/health     健康检查
"""

import os
import re
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
from format_reader import extract_text
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
async def convert(file: UploadFile = File(...), title: str = Form(""), author: str = Form(""),
                   chapters_json: str = Form("")):
    """上传小说文本，返回生成的剧本 YAML。

    返回 JSON:
      { "status": "ok", "yaml": "...", "meta": {...}, "warnings": [...], "errors": [...] }
    或:
      { "status": "error", "message": "..." }
    """
    # ── 校验格式 ──
    fn = file.filename or "untitled.txt"
    ext = fn.rsplit(".", 1)[-1].lower() if "." in fn else ""
    supported = ("txt", "text", "md", "markdown", "docx", "epub")
    if ext not in supported:
        return JSONResponse({
            "status": "error",
            "message": f"不支持 .{ext} 格式，支持: {', '.join(supported)}"
        }, status_code=400)

    content = await file.read()
    file_size_mb = len(content) / (1024 * 1024)
    if file_size_mb > MAX_FILE_SIZE_MB:
        return JSONResponse({
            "status": "error",
            "message": f"文件过大 ({file_size_mb:.1f}MB)，限制 {MAX_FILE_SIZE_MB}MB"
        }, status_code=400)

    try:
        text = extract_text(content, fn)
    except ValueError as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=400)
    except Exception as e:
        logger.error(f"[Format] 解析失败: {e}")
        return JSONResponse({"status": "error", "message": f"文件解析失败: {e}"}, status_code=400)

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

    # ── 章节筛选（用户选择部分章节转换）──
    if chapters_json:
        try:
            selected = json.loads(chapters_json)
            if isinstance(selected, list) and len(selected) > 0:
                before = len(chapters)
                # 按章节编号匹配（支持 int 和 str）
                selected_set = {str(s) for s in selected}
                chapters = [c for c in chapters if str(c["number"]) in selected_set]
                logger.info(f"[Convert] 用户选择 {len(chapters)}/{before} 章")
                if len(chapters) < 1:
                    return JSONResponse({"status": "error", "message": "未选择任何有效章节"}, status_code=400)
        except (json.JSONDecodeError, TypeError):
            pass

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

    # 保存到 output/ 目录
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
    os.makedirs(output_dir, exist_ok=True)
    safe_title = re.sub(r'[\\/:*?"<>|]', '_', script["meta"].get("title", "script"))
    out_filename = f"{safe_title}.yaml"
    out_path = os.path.join(output_dir, out_filename)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(yaml_str)

    logger.info(f"[Convert] 完成! {len(script['scenes'])} 场景 → {out_path}")

    return {
        "status": "ok",
        "yaml": yaml_str,
        "output_file": out_path,
        "output_filename": out_filename,
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


@app.post("/api/preview")
async def preview(file: UploadFile = File(...)):
    """上传文件 → 返回章节列表 + 体裁检测（不转换）"""
    fn = file.filename or "untitled.txt"
    ext = fn.rsplit(".", 1)[-1].lower() if "." in fn else ""
    supported = ("txt", "text", "md", "markdown", "docx", "epub")
    if ext not in supported:
        return JSONResponse({"status": "error", "message": f"不支持 .{ext}"}, status_code=400)

    content = await file.read()
    try:
        text = extract_text(content, fn)
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=400)

    chapters = split_chapters(text)
    if not chapters:
        return JSONResponse({"status": "error", "message": "未检测到章节"}, status_code=400)

    # 体裁检测：取开头 1000 字给 LLM 判断
    genre = _detect_genre(text[:1500])

    return {
        "status": "ok",
        "filename": fn,
        "total_chars": len(text),
        "chapter_count": len(chapters),
        "genre": genre,
        "chapters": [
            {"num": c["number"], "title": c["title"], "chars": c["char_count"]}
            for c in chapters
        ],
    }


def _detect_genre(text_sample: str) -> str:
    """快速体裁检测（取关键词，不调 LLM）"""
    import re
    keywords = {
        "武侠": ["剑", "江湖", "门派", "内力", "武林", "侠", "功法"],
        "科幻": ["飞船", "星球", "外星", "AI", "机器人", "量子", "基因"],
        "奇幻": ["魔法", "龙", "精灵", "咒语", "王国", "巫师", "魔"],
        "悬疑": ["凶手", "侦探", "尸体", "密室", "线索", "谋杀"],
        "爱情": ["爱情", "恋爱", "婚礼", "求婚", "未婚", "情侣"],
        "恐怖": ["鬼", "幽灵", "诅咒", "血", "恐怖", "噩梦"],
        "历史": ["皇帝", "将军", "战争", "朝代", "陛下", "起义"],
        "文学经典": [],
    }
    scores = {}
    for genre, words in keywords.items():
        score = sum(text_sample.lower().count(w.lower()) for w in words)
        if score > 0:
            scores[genre] = score

    if scores:
        return max(scores, key=scores.get)

    # 检查是否英文经典文学
    classic_markers = ["CHAPTER", "Mr.", "Mrs.", "Miss", "Lady", "Lord", "gentleman"]
    classic_score = sum(text_sample.count(m) for m in classic_markers)
    if classic_score > 3:
        return "文学经典"

    return "通用"


@app.get("/api/schema")
async def get_schema_doc():
    """返回 Schema 文档（Markdown）"""
    docs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")
    doc_path = os.path.join(docs_dir, "yaml-schema.md")
    if os.path.exists(doc_path):
        with open(doc_path, "r", encoding="utf-8") as f:
            return {"content": f.read()}
    return {"content": "# Schema 文档\n\n（尚未生成）"}


@app.get("/api/download/{filename}")
async def download_yaml(filename: str):
    """服务端下载 YAML 文件"""
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
    file_path = os.path.join(output_dir, filename)
    if not os.path.exists(file_path):
        return JSONResponse({"status": "error", "message": "文件不存在"}, status_code=404)
    return FileResponse(file_path, media_type="text/yaml", filename=filename)


if __name__ == "__main__":
    import uvicorn
    logger.info(f"Novel2Script 启动: http://{HOST}:{PORT}")
    logger.info(f"  LLM 模式: {LLM_MODE}")
    base_url, api_key, model = get_llm_config()
    logger.info(f"  模型: {model} @ {base_url}")
    uvicorn.run(app, host=HOST, port=PORT)
