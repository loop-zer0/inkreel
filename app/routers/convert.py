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


# ══════════════════════════════════════════════════════════════
# 自动合并：转换完成后自动拼装完整 YAML
# ══════════════════════════════════════════════════════════════

def _auto_merge(script_id: int, novel_id: int, title_override: str = None) -> dict:
    """将当前剧本的所有已转换章节合并为完整 YAML 并存入 scripts.yaml_content。
    如果剧本被手动编辑过则跳过。
    返回 {"merged": bool, "yaml": str|None, "stats": dict|None}
    """
    if script_repo.is_manually_edited(script_id):
        logger.info(f"[AutoMerge] 剧本 {script_id} 已手动编辑，跳过自动合并")
        return {"merged": False, "yaml": None, "stats": None}

    script = script_repo.get_script(script_id)
    if not script:
        return {"merged": False, "yaml": None, "stats": None}

    chapters_data = script.get("chapters", [])
    if not chapters_data:
        return {"merged": False, "yaml": None, "stats": None}

    novel = novel_repo.get_novel(novel_id)
    if not novel:
        return {"merged": False, "yaml": None, "stats": None}

    # 收集所有场景
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
        except Exception as e:
            logger.warning(f"[AutoMerge] 解析第{ch['chapter_number']}章 YAML 失败: {e}")

    if not all_scenes:
        return {"merged": False, "yaml": None, "stats": None}

    # 提取人物
    chapters_for_extract = novel_repo.get_chapters_with_content(novel_id)
    characters = extract_characters(chapters_for_extract, novel_id)

    # 合并
    final_script = merge(characters, all_scenes)
    final_script["meta"]["title"] = title_override or novel.get("title", "（未命名）")
    final_script["meta"]["original_author"] = novel.get("author", "（未知）")

    yaml_str = dump_yaml(final_script)

    script_repo.auto_save_yaml(
        script_id, yaml_str,
        len(final_script.get("characters", [])),
        len(final_script.get("scenes", [])),
    )

    # 输出文件
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    safe_title = re.sub(r'[\\/:*?"<>|]', '_', final_script["meta"].get("title", "script"))
    out_path = os.path.join(OUTPUT_DIR, f"{safe_title}.yaml")
    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(yaml_str)
    except Exception as e:
        logger.warning(f"[AutoMerge] 写入文件失败: {e}")

    logger.info(
        f"[AutoMerge] 剧本 {script_id}: {len(final_script.get('characters', []))} 人, "
        f"{len(final_script.get('scenes', []))} 场景"
    )
    return {
        "merged": True, "yaml": yaml_str, "output_file": out_path,
        "stats": {
            "chapters": len(chapters_data),
            "characters": len(final_script.get("characters", [])),
            "scenes": len(final_script.get("scenes", [])),
            "acts": len(final_script.get("acts", [])),
        },
    }


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
    chapters_for_extract = novel_repo.get_chapters_with_content(novel_id)
    characters = await asyncio.to_thread(extract_characters, chapters_for_extract, novel_id)

    results = []
    for cn in chapter_numbers:
        cn = float(cn)
        chapter_info = novel_repo.get_chapter_info(novel_id, cn)
        if not chapter_info:
            results.append({"chapter_number": cn, "status": "error", "message": "章节不存在"})
            continue

        # 检查是否已有转换结果（当前剧本或其他剧本均可）→ 直接复用，避免重复调用 LLM
        existing_chapters = script_repo.get_chapter_scenes(novel_id, cn)
        reused_yaml = None
        if existing_chapters:
            for ec in existing_chapters:
                if ec.get("yaml_content"):
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

    # 自动合并
    merge_result = _auto_merge(script["id"], novel_id)

    return {
        "status": "ok",
        "script_id": script["id"],
        "results": results,
        "generated_chapters": sorted(generated),
        "total_chapters": len(novel.get("chapters", [])),
        "merged_yaml": merge_result.get("yaml"),
        "merged_stats": merge_result.get("stats"),
    }


# ══════════════════════════════════════════════════════════════
# SSE 流式批量转换 — 并行 + 逐章推送
# ══════════════════════════════════════════════════════════════

import json as _json
from fastapi.responses import StreamingResponse


def _process_one_chapter(novel_id: int, cn: float, script: dict,
                         characters: list) -> dict:
    """在线程中处理单章：检测复用 → 调用 LLM → 入库。返回结果 dict"""
    chapter_info = novel_repo.get_chapter_info(novel_id, cn)
    if not chapter_info:
        return {"chapter_number": cn, "status": "error", "message": "章节不存在"}

    # 检查已有转换结果（跨剧本复用）
    existing_chapters = script_repo.get_chapter_scenes(novel_id, cn)
    reused_yaml = None
    if existing_chapters:
        for ec in existing_chapters:
            if ec.get("yaml_content"):
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
        logger.info(f"[BatchStream] 复用已有场景: chapter={cn} → {sc_count}场景")
    else:
        chapter = {
            "number": chapter_info["chapter_number"],
            "title": chapter_info["title"],
            "content": chapter_info["content"],
        }
        context_text = build_chapter_context(novel_id, cn, characters)
        scenes, summary = convert_chapter(chapter, characters, novel_id, script["id"], context_text)

        if not scenes:
            return {"chapter_number": cn, "status": "error", "message": "转换失败"}

        chapter_yaml = dump_yaml({
            "meta": {"source_chapter": cn, "chapter_title": chapter_info["title"]},
            "scenes": scenes,
        })
        sc_count = len(scenes)

    # 入库（每个线程独立 get_db 连接，SQLite WAL 模式安全）
    script_repo.save_script_chapter(script["id"], novel_id, cn, chapter_yaml, sc_count)
    if summary:
        context_repo.save_chapter_context(novel_id, cn, summary=summary)

    return {
        "type": "chapter",
        "chapter_number": cn,
        "status": "ok",
        "yaml": chapter_yaml,
        "scenes_count": sc_count,
        "summary": summary,
        "reused": reused_yaml is not None,
    }


@router.post("/novels/{novel_id}/convert/batch/stream")
async def convert_batch_stream(novel_id: int, request: Request):
    """并行批量转换 + SSE 流式推送（每完成一章即推送给前端）"""
    req = await request.json()
    chapter_numbers = req.get("chapter_numbers", [])
    if not chapter_numbers:
        return JSONResponse({"status": "error", "message": "缺少 chapter_numbers"}, status_code=400)

    novel = novel_repo.get_novel(novel_id)
    if not novel:
        return JSONResponse({"status": "error", "message": "小说不存在"}, status_code=404)

    script = script_repo.get_or_create_draft_script(novel_id, novel.get("title", "（未命名）"))
    chapters_for_extract = novel_repo.get_chapters_with_content(novel_id)
    characters = await asyncio.to_thread(extract_characters, chapters_for_extract, novel_id)

    async def event_stream():
        total = len(chapter_numbers)
        completed = 0
        success = 0
        failed = 0

        # 并发启动所有章节任务
        tasks = []
        for cn in chapter_numbers:
            tasks.append(asyncio.to_thread(
                _process_one_chapter, novel_id, float(cn), script, characters))

        # 先推送一行注释触发连接
        yield ":connected\n\n"

        # 逐章推送结果（as_completed 保证谁先完成先推谁）
        for coro in asyncio.as_completed(tasks):
            completed += 1
            try:
                result = await coro
            except Exception as e:
                result = {
                    "type": "chapter",
                    "chapter_number": 0,
                    "status": "error",
                    "message": str(e),
                }
                logger.error(f"[BatchStream] 章节处理异常: {e}")

            if result.get("status") == "ok":
                success += 1
            else:
                failed += 1

            result["progress"] = f"{completed}/{total}"
            yield f"data: {_json.dumps(result, ensure_ascii=False)}\n\n"

        # 自动合并
        merge_result = _auto_merge(script["id"], novel_id)
        yield f"data: {_json.dumps({'type': 'merge', **merge_result}, ensure_ascii=False)}\n\n"

        # 完成
        generated = script_repo.get_generated_chapter_numbers(novel_id, script["id"])
        yield f"data: {_json.dumps({'type': 'done', 'total': total, 'success': success, 'failed': failed, 'script_id': script['id'], 'generated_chapters': sorted(generated)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


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

    # 检查是否已有转换结果（当前剧本或其他剧本均可）→ 直接复用，不走 LLM
    existing_chapters = script_repo.get_chapter_scenes(novel_id, chapter_num)
    reused_yaml = None
    if existing_chapters:
        for ec in existing_chapters:
            if ec.get("yaml_content"):
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
        # 人物提取（优先走缓存；需要章节正文）
        chapters_for_extract = novel_repo.get_chapters_with_content(novel_id) or [chapter]
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

    # 自动合并：转换完成后立即拼装完整 YAML
    merge_result = _auto_merge(script["id"], novel_id)

    return {
        "status": "ok",
        "chapter_number": chapter_num,
        "yaml": chapter_yaml,
        "merged_yaml": merge_result.get("yaml"),
        "scenes_count": scenes_count,
        "summary": summary,
        "script_id": script["id"],
        "generated_chapters": sorted(generated),
        "total_chapters": len(novel.get("chapters", [])),
        "reused": reused_yaml is not None,
    }


# ── 锁定剧本（发布最终版本，禁止后续修改）──

@router.post("/scripts/{script_id}/merge")
async def lock_script(script_id: int, req: dict = None):
    """锁定剧本：将当前草稿冻结为完整版本。合并已自动完成，此接口只改状态。"""
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

    # 确保 yaml_content 是最新的（防止自动合并被跳过的情况）
    yaml_str = script.get("yaml_content", "")
    if not yaml_str:
        merge_result = _auto_merge(script_id, novel_id,
                                   title_override=(req or {}).get("title") if req else None)
        yaml_str = merge_result.get("yaml", "")
        if not yaml_str:
            return JSONResponse({"status": "error", "message": "合并失败"}, status_code=500)

    # 标题处理
    raw_title = (req or {}).get("title") if req else None
    title = str(raw_title).strip() if raw_title and str(raw_title).strip() else novel.get("title", "（未命名）")

    char_count = script.get("character_count", 0)
    scene_count = script.get("scene_count", 0)

    script_repo.finalize_script(script_id, yaml_str, char_count, scene_count)

    return {
        "status": "ok",
        "yaml": yaml_str,
        "script_id": script_id,
        "message": "剧本已锁定",
        "stats": {
            "chapters": len(chapters_data),
            "characters": char_count,
            "scenes": scene_count,
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
