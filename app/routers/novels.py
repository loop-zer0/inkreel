"""小说导入 + 仓库管理路由"""

import json
import logging
import asyncio

from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import JSONResponse

from app.config import MAX_FILE_SIZE_MB
from app.services.importer import preview_file, import_novel
from app.repositories import novel as novel_repo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["novels"])


# ── 预览上传 ──

@router.post("/novels/preview")
async def preview_upload(file: UploadFile = File(...)):
    """上传文件 → 章节预览（不入库，不调 LLM）"""
    content = await file.read()
    fn = file.filename or "untitled.txt"

    file_size_mb = len(content) / (1024 * 1024)
    if file_size_mb > MAX_FILE_SIZE_MB:
        return JSONResponse({
            "status": "error",
            "message": f"文件过大 ({file_size_mb:.1f}MB)，限制 {MAX_FILE_SIZE_MB}MB",
        }, status_code=400)

    result = preview_file(content, fn)
    if result["status"] == "error":
        return JSONResponse(result, status_code=400)

    # 暂存文本和章节供后续 import 使用（通过内存，不落地）
    router._preview_cache = {
        "filename": fn,
        "text": result.pop("_text"),
        "chapters": result.pop("_chapters"),
        "ext": result.pop("_ext"),
        "genre": result["genre"],
    }
    return result


router._preview_cache = {}


# ── 确认导入 ──

@router.post("/novels/import")
async def confirm_import(req: dict):
    """确认导入，将预览的小说存入仓库"""
    cache = getattr(router, '_preview_cache', {})
    if not cache or not cache.get("text"):
        return JSONResponse({"status": "error", "message": "请先上传文件预览"}, status_code=400)

    title = req.get("title", cache["filename"])
    author = req.get("author", "")

    try:
        novel_id = import_novel(
            title=title,
            author=author,
            filename=cache["filename"],
            text=cache["text"],
            chapters=cache["chapters"],
            ext=cache["ext"],
            genre=cache.get("genre", ""),
        )
        # 清除缓存
        router._preview_cache = {}
        return {"status": "ok", "novel_id": novel_id, "message": "导入成功"}
    except Exception as e:
        logger.error(f"[Novels] 导入失败: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


# ── 一键转换（上传 + 导入 + 全量转换 + 合并）──

@router.post("/novels/quick-convert")
async def quick_convert(file: UploadFile = File(...), title: str = Form(""),
                        author: str = Form(""), chapters_json: str = Form("")):
    """上传 → 导入 → 全量转换 → 合并 → 返回 YAML"""
    from app.services.extractor import extract_characters
    from app.services.converter import convert_all
    from app.services.merger import merge
    from app.schemas.validator import validate, dump_yaml
    from app.repositories.script import save_script, save_script_chapter

    # 1. 预览
    content = await file.read()
    fn = file.filename or "untitled.txt"
    file_size_mb = len(content) / (1024 * 1024)
    if file_size_mb > MAX_FILE_SIZE_MB:
        return JSONResponse({
            "status": "error",
            "message": f"文件过大 ({file_size_mb:.1f}MB)，限制 {MAX_FILE_SIZE_MB}MB",
        }, status_code=400)

    preview = preview_file(content, fn)
    if preview["status"] == "error":
        return JSONResponse(preview, status_code=400)

    text = preview.pop("_text")
    chapters = preview.pop("_chapters")
    ext = preview.pop("_ext")

    # 章节筛选
    if chapters_json:
        try:
            selected = json.loads(chapters_json)
            if isinstance(selected, list) and selected:
                selected_set = {str(s) for s in selected}
                chapters = [c for c in chapters if str(c["number"]) in selected_set]
                if not chapters:
                    return JSONResponse({"status": "error", "message": "未选择任何有效章节"}, status_code=400)
        except (json.JSONDecodeError, TypeError):
            pass

    if len(chapters) < 1:
        return JSONResponse({
            "status": "error",
            "message": "未检测到有效章节",
        }, status_code=400)

    # 2. 导入
    novel_id = import_novel(
        title=title or preview["filename"],
        author=author or "（未知）",
        filename=preview["filename"],
        text=text, chapters=chapters, ext=ext,
        genre=preview.get("genre", ""),
    )

    # 3. 提取人物
    characters = await asyncio.to_thread(extract_characters, chapters, novel_id)
    logger.info(f"[QuickConvert] 人物提取: {len(characters)} 人")

    # 4. 全量转换
    all_scenes = await asyncio.to_thread(convert_all, chapters, characters)
    if not all_scenes:
        return JSONResponse({"status": "error", "message": "转换失败：未能生成任何场景"}, status_code=500)

    # 5. 合并
    script = merge(characters, all_scenes)
    if title:
        script["meta"]["title"] = title
    if author:
        script["meta"]["original_author"] = author

    validation_errors = validate(script)
    yaml_str = dump_yaml(script)

    # 6. 保存到仓库
    final_script_id = save_script(
        novel_id=novel_id,
        title=script["meta"].get("title", "（未命名）"),
        yaml_content=yaml_str,
        character_count=len(script["characters"]),
        scene_count=len(script["scenes"]),
        status="complete",
    )

    # 逐章保存
    scenes_by_chapter = {}
    for s in all_scenes:
        cn = s.get("source_chapter", s.get("_chapter_num", 0))
        scenes_by_chapter.setdefault(cn, []).append(s)
    for cn, ch_scenes in scenes_by_chapter.items():
        ch_yaml = dump_yaml({"meta": {"source_chapter": cn}, "scenes": ch_scenes})
        save_script_chapter(final_script_id, novel_id, float(cn), ch_yaml, len(ch_scenes))

    # 7. 保存到 output/
    import re, os
    from app.config import OUTPUT_DIR
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    safe_title = re.sub(r'[\\/:*?"<>|]', '_', script["meta"].get("title", "script"))
    out_path = os.path.join(OUTPUT_DIR, f"{safe_title}.yaml")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(yaml_str)

    return {
        "status": "ok",
        "yaml": yaml_str,
        "output_file": out_path,
        "novel_id": novel_id,
        "script_id": final_script_id,
        "meta": script["meta"],
        "stats": {
            "chapters": len(chapters),
            "characters": len(script["characters"]),
            "scenes": len(script["scenes"]),
            "acts": len(script.get("acts", [])),
            "total_chars": len(text),
        },
        "errors": validation_errors,
    }


# ── 仓库 CRUD ──

@router.get("/novels")
async def list_novels():
    """仓库列表"""
    try:
        novels = novel_repo.list_novels()
        return {"status": "ok", "novels": novels}
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@router.get("/novels/{novel_id}")
async def get_novel(novel_id: int):
    """小说详情（含章节和剧本）"""
    novel = novel_repo.get_novel(novel_id)
    if not novel:
        return JSONResponse({"status": "error", "message": "小说不存在"}, status_code=404)
    return {"status": "ok", "novel": novel}


@router.put("/novels/{novel_id}")
async def update_novel_meta(novel_id: int, req: dict):
    """更新小说元信息"""
    ok = novel_repo.update_novel(
        novel_id,
        title=req.get("title"),
        author=req.get("author"),
        genre=req.get("genre"),
    )
    if not ok:
        return JSONResponse({"status": "error", "message": "更新失败"}, status_code=500)
    return {"status": "ok", "message": "已更新"}


# ── 章节内容（含正文）──

@router.get("/novels/{novel_id}/chapters/{chapter_num}/content")
async def get_chapter_content(novel_id: int, chapter_num: float):
    """获取单章完整内容（正文 + 元信息），供编辑器使用"""
    ch = novel_repo.get_chapter_info(novel_id, chapter_num)
    if not ch:
        return JSONResponse({"status": "error", "message": "章节不存在"}, status_code=404)
    return {"status": "ok", "chapter": ch}


# ── 章节编辑 ──

@router.put("/novels/{novel_id}/chapters/{chapter_id}")
async def update_chapter(novel_id: int, chapter_id: int, req: dict):
    """更新小说章节内容"""
    ok = novel_repo.update_chapter(
        chapter_id,
        title=req.get("title"),
        content=req.get("content"),
    )
    if not ok:
        return JSONResponse({"status": "error", "message": "更新失败"}, status_code=500)
    return {"status": "ok", "message": "章节已更新"}


@router.post("/novels/{novel_id}/append")
async def append_chapters(novel_id: int, file: UploadFile = File(...)):
    """上传文件追加新章节（自动跳过已有章节号）"""
    novel = novel_repo.get_novel(novel_id)
    if not novel:
        return JSONResponse({"status": "error", "message": "小说不存在"}, status_code=404)

    content = await file.read()
    from app.services.importer import preview_file
    preview = preview_file(content, file.filename or "untitled.txt")
    if preview["status"] == "error":
        return JSONResponse(preview, status_code=400)

    chapters = preview.pop("_chapters")
    if not chapters:
        return JSONResponse({"status": "error", "message": "未检测到有效章节"}, status_code=400)

    result = novel_repo.append_chapters(novel_id, chapters)
    return {
        "status": "ok",
        "message": f"已追加 {result['added']} 章，跳过 {result['skipped']} 章（已存在）",
        "added": result["added"],
        "skipped": result["skipped"],
    }


# ── 智能章节同步 ──

@router.post("/novels/{novel_id}/sync-preview")
async def sync_preview(novel_id: int, file: UploadFile = File(...)):
    """上传文件 → 对比已有章节 → 返回差异报告"""
    novel = novel_repo.get_novel(novel_id)
    if not novel:
        return JSONResponse({"status": "error", "message": "小说不存在"}, status_code=404)

    content = await file.read()
    from app.services.importer import preview_file
    preview = preview_file(content, file.filename or "untitled.txt")
    if preview["status"] == "error":
        return JSONResponse(preview, status_code=400)

    incoming = preview.pop("_chapters")
    if not incoming:
        return JSONResponse({"status": "error", "message": "未检测到有效章节"}, status_code=400)

    # 已有章节（含正文，用于内容比对）
    existing = novel_repo.get_chapters_with_content(novel_id)
    existing_map = {}  # chapter_number → chapter
    for ch in existing:
        existing_map[ch["chapter_number"]] = ch

    new_chapters = []
    modified_chapters = []
    unchanged = 0

    for inc in incoming:
        cn = inc.get("number", 0)
        inc_content = inc.get("content", "")
        old = existing_map.get(cn)

        if old is None:
            new_chapters.append({
                "chapter_number": cn,
                "title": inc.get("title", ""),
                "char_count": len(inc_content),
            })
        elif old.get("content", "").strip() != inc_content.strip():
            modified_chapters.append({
                "chapter_number": cn,
                "title": inc.get("title", ""),
                "char_count": len(inc_content),
                "chapter_id": old["id"],
                "old_char_count": old.get("char_count", 0),
            })
        else:
            unchanged += 1

    # 缓存用于后续 apply
    router._sync_cache = {
        "novel_id": novel_id,
        "incoming": incoming,
        "new_numbers": {c["chapter_number"] for c in new_chapters},
        "mod_numbers": {c["chapter_number"] for c in modified_chapters},
    }

    return {
        "status": "ok",
        "filename": file.filename,
        "total_incoming": len(incoming),
        "existing": len(existing),
        "new": new_chapters,
        "modified": modified_chapters,
        "unchanged": unchanged,
    }


@router.post("/novels/{novel_id}/sync-apply")
async def sync_apply(novel_id: int, req: dict):
    """应用同步操作"""
    cache = getattr(router, '_sync_cache', {})
    if not cache or cache.get("novel_id") != novel_id:
        return JSONResponse({"status": "error", "message": "请先执行 sync-preview"}, status_code=400)

    incoming = cache["incoming"]
    add_numbers = set(req.get("add", []))
    update_numbers = set(req.get("update", []))

    to_add = [c for c in incoming if c.get("number", 0) in add_numbers]
    to_update = [c for c in incoming if c.get("number", 0) in update_numbers]

    added = novel_repo.bulk_add_chapters(novel_id, to_add) if to_add else 0
    updated = novel_repo.bulk_update_chapters(novel_id, to_update) if to_update else 0

    router._sync_cache = {}
    return {"status": "ok", "added": added, "updated": updated}


router._sync_cache = {}


@router.delete("/novels/{novel_id}")
async def delete_novel(novel_id: int):
    """删除小说及关联数据"""
    ok = novel_repo.delete_novel(novel_id)
    if ok is None:
        return JSONResponse({"status": "error", "message": "小说不存在"}, status_code=404)
    if not ok:
        return JSONResponse({"status": "error", "message": "删除失败"}, status_code=500)
    return {"status": "ok", "message": "已删除"}
