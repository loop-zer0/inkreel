"""逐章转换 + 合并路由"""

import asyncio
import logging
import re
import os
import yaml

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.services.extractor import extract_characters
from app.services.converter import convert_chapter, build_chapter_context
from app.services.merger import merge
from app.schemas.validator import dump_yaml
from app.repositories import novel as novel_repo
from app.repositories import script as script_repo
from app.repositories import context as context_repo
from app.config import OUTPUT_DIR

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["convert"])


# ── 批量转换（必须注册在单章转换前面，否则 /convert/batch 会被 {chapter_num} 吃掉）──

@router.post("/novels/{novel_id}/convert/batch")
async def convert_batch(novel_id: int, request: Request):
    """批量转换选中章节"""
    req = await request.json()
    chapter_numbers = req.get("chapter_numbers", [])
    if not chapter_numbers:
        return JSONResponse({"status": "error", "message": "缺少 chapter_numbers"}, status_code=400)

    novel = novel_repo.get_novel(novel_id)
    if not novel:
        return JSONResponse({"status": "error", "message": "小说不存在"}, status_code=404)

    script = script_repo.get_or_create_draft_script(novel_id, novel.get("title", "（未命名）"))
    chapters_for_extract = novel.get("chapters", [])
    characters = await asyncio.to_thread(extract_characters, chapters_for_extract, novel_id)

    results = []
    for cn in chapter_numbers:
        cn = float(cn)
        chapter_info = novel_repo.get_chapter_info(novel_id, cn)
        if not chapter_info:
            results.append({"chapter_number": cn, "status": "error", "message": "章节不存在"})
            continue

        # 检查是否已在其他剧本中转换过 → 直接复用
        existing_chapters = script_repo.get_chapter_scenes(novel_id, cn)
        reused_yaml = None
        if existing_chapters:
            for ec in existing_chapters:
                if ec["script_id"] != script["id"] and ec.get("yaml_content"):
                    reused_yaml = ec["yaml_content"]
                    break

        if reused_yaml:
            try:
                reused_data = yaml.safe_load(reused_yaml)
                reused_scenes = reused_data.get("scenes", []) if isinstance(reused_data, dict) else []
            except Exception:
                reused_scenes = []
            chapter_yaml = reused_yaml
            sc_count = len(reused_scenes)
            summary = None
            logger.info(f"[BatchConvert] 复用已有场景: chapter={cn} → {sc_count}场景")
        else:
            chapter = {"number": chapter_info["chapter_number"], "title": chapter_info["title"],
                       "content": chapter_info["content"]}
            context_text = build_chapter_context(novel_id, cn, characters)

            scenes, summary = await asyncio.to_thread(
                convert_chapter, chapter, characters, novel_id, script["id"], context_text)

            if not scenes:
                results.append({"chapter_number": cn, "status": "error", "message": "转换失败"})
                continue

            chapter_yaml = dump_yaml({
                "meta": {"source_chapter": cn, "chapter_title": chapter_info["title"]},
                "scenes": scenes,
            })
            sc_count = len(scenes)

        script_repo.save_script_chapter(script["id"], novel_id, cn, chapter_yaml, sc_count)
        if summary:
            context_repo.save_chapter_context(novel_id, cn, summary=summary)

        results.append({
            "chapter_number": cn, "status": "ok", "yaml": chapter_yaml,
            "scenes_count": sc_count, "summary": summary, "reused": reused_yaml is not None,
        })

    generated = script_repo.get_generated_chapter_numbers(novel_id, script["id"])
    can_merge = len(generated) >= 3

    return {
        "status": "ok",
        "script_id": script["id"],
        "results": results,
        "can_merge": can_merge,
        "generated_chapters": sorted(generated),
        "total_chapters": len(novel.get("chapters", [])),
    }


# ── 单章转换 ──

@router.post("/novels/{novel_id}/convert/{chapter_num}")
async def convert_single_chapter(novel_id: int, chapter_num: float,
                                 req: dict = None):
    """转换小说中的某一章为剧本场景"""
    novel = novel_repo.get_novel(novel_id)
    if not novel:
        return JSONResponse({"status": "error", "message": "小说不存在"}, status_code=404)

    chapter_info = novel_repo.get_chapter_info(novel_id, chapter_num)
    if not chapter_info:
        return JSONResponse(
            {"status": "error", "message": f"章节 {chapter_num} 不存在"}, status_code=404)

    chapter = {
        "number": chapter_info["chapter_number"],
        "title": chapter_info["title"],
        "content": chapter_info["content"],
    }

    # 获取或创建草稿剧本
    script = script_repo.get_or_create_draft_script(novel_id, novel.get("title", "（未命名）"))

    # 检查是否已在其他剧本中转换过 → 直接复用，不走 LLM
    existing_chapters = script_repo.get_chapter_scenes(novel_id, chapter_num)
    reused_yaml = None
    if existing_chapters:
        for ec in existing_chapters:
            if ec["script_id"] != script["id"] and ec.get("yaml_content"):
                reused_yaml = ec["yaml_content"]
                break

    if reused_yaml:
        # 直接复制到当前草稿
        try:
            reused_data = yaml.safe_load(reused_yaml)
            reused_scenes = reused_data.get("scenes", []) if isinstance(reused_data, dict) else []
        except Exception:
            reused_scenes = []
        chapter_yaml = reused_yaml
        scenes_count = len(reused_scenes)
        summary = None
        logger.info(f"[Convert] 复用已有场景: novel_id={novel_id}, chapter={chapter_num} → {scenes_count}场景")
    else:
        # 人物提取（优先走缓存）
        chapters_for_extract = novel.get("chapters", []) or [chapter]
        characters = await asyncio.to_thread(extract_characters, chapters_for_extract, novel_id)

        # 构建上下文
        context_text = build_chapter_context(novel_id, chapter_num, characters)

        logger.info(f"[Convert] 逐章转换: novel_id={novel_id}, chapter={chapter_num}")
        scenes, summary = await asyncio.to_thread(
            convert_chapter, chapter, characters, novel_id, script["id"], context_text)

        if not scenes:
            return JSONResponse(
                {"status": "error", "message": f"第{chapter_num}章转换失败，未能生成场景"}, status_code=500)

        chapter_yaml = dump_yaml({
            "meta": {"source_chapter": chapter_num, "chapter_title": chapter_info["title"]},
            "scenes": scenes,
        })
        scenes_count = len(scenes)

        if summary:
            context_repo.save_chapter_context(
                novel_id=novel_id, chapter_number=chapter_num, summary=summary)

    script_repo.save_script_chapter(script["id"], novel_id, chapter_num, chapter_yaml, scenes_count)

    generated = script_repo.get_generated_chapter_numbers(novel_id, script["id"])
    can_merge = len(generated) >= 3

    return {
        "status": "ok",
        "chapter_number": chapter_num,
        "yaml": chapter_yaml,
        "scenes_count": scenes_count,
        "summary": summary,
        "script_id": script["id"],
        "generated_chapters": sorted(generated),
        "total_chapters": len(novel.get("chapters", [])),
        "can_merge": can_merge,
        "reused": reused_yaml is not None,
    }


# ── 合并为完整剧本 ──

@router.post("/scripts/{script_id}/merge")
async def merge_script(script_id: int, req: dict = None):
    """将逐章场景合并为完整剧本 YAML"""
    script = script_repo.get_script(script_id)
    if not script:
        return JSONResponse({"status": "error", "message": "剧本不存在"}, status_code=404)

    novel_id = script["novel_id"]
    novel = novel_repo.get_novel(novel_id)
    if not novel:
        return JSONResponse({"status": "error", "message": "小说不存在"}, status_code=404)

    chapters_data = script.get("chapters", [])
    if not chapters_data:
        return JSONResponse({"status": "error", "message": "该剧本还没有生成任何章节场景"}, status_code=400)

    all_scenes = []
    for ch in sorted(chapters_data, key=lambda c: c["chapter_number"]):
        try:
            ch_data = yaml.safe_load(ch["yaml_content"])
            if isinstance(ch_data, dict):
                scenes = ch_data.get("scenes", [])
                for s in scenes:
                    s["source_chapter"] = ch["chapter_number"]
                    s["_chapter_num"] = ch["chapter_number"]
                all_scenes.extend(scenes)
                logger.info(f"[Merge] 第{ch['chapter_number']}章: {len(scenes)} 场景")
        except Exception as e:
            logger.warning(f"[Merge] 解析第{ch['chapter_number']}章 YAML 失败: {e}")

    if len(all_scenes) < 3:
        return JSONResponse(
            {"status": "error", "message": f"场景数不足 ({len(all_scenes)}), 需要至少3个"}, status_code=400)

    chapters_for_extract = novel.get("chapters", [])
    characters = await asyncio.to_thread(extract_characters, chapters_for_extract, novel_id)

    final_script = merge(characters, all_scenes)
    # 处理 title：前端可能传 null / 空字符串 / 不传
    raw_title = (req or {}).get("title") if req else None
    if raw_title and str(raw_title).strip():
        final_script["meta"]["title"] = str(raw_title).strip()
    else:
        final_script["meta"]["title"] = novel.get("title", "（未命名）")
    final_script["meta"]["original_author"] = novel.get("author", "（未知）")

    yaml_str = dump_yaml(final_script)

    script_repo.finalize_script(
        script_id, yaml_str,
        len(final_script.get("characters", [])),
        len(final_script.get("scenes", [])),
    )

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    safe_title = re.sub(r'[\\/:*?"<>|]', '_', final_script["meta"].get("title", "script"))
    out_path = os.path.join(OUTPUT_DIR, f"{safe_title}.yaml")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(yaml_str)

    return {
        "status": "ok",
        "yaml": yaml_str,
        "script_id": script_id,
        "output_file": out_path,
        "stats": {
            "chapters": len(chapters_data),
            "characters": len(final_script.get("characters", [])),
            "scenes": len(final_script.get("scenes", [])),
            "acts": len(final_script.get("acts", [])),
        },
    }


# ── 从仓库重建预览（用于重新打开小说）──

@router.get("/novels/{novel_id}/preview")
async def reload_preview(novel_id: int):
    """从仓库获取小说的预览数据（章节列表 + 已转状态）"""
    novel = novel_repo.get_novel(novel_id)
    if not novel:
        return JSONResponse({"status": "error", "message": "小说不存在"}, status_code=404)

    generated = script_repo.get_generated_chapter_numbers(novel_id)

    return {
        "status": "ok",
        "filename": novel["filename"],
        "total_chars": novel["total_chars"],
        "chapter_count": len(novel.get("chapters", [])),
        "genre": novel["genre"],
        "novel_id": novel_id,
        "chapters": [
            {"num": c.get("chapter_number", c.get("number")),
             "title": c["title"],
             "chars": c.get("char_count", len(c.get("content", "")))}
            for c in novel.get("chapters", [])
        ],
        "generated_chapters": sorted(generated),
    }
