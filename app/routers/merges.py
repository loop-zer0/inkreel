"""合并剧本路由"""

import asyncio
import logging
import yaml

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.repositories import novel as novel_repo
from app.repositories import script as script_repo
from app.repositories import merged_script as merge_repo
from app.services.extractor import extract_characters
from app.services.merger import merge
from app.schemas.validator import dump_yaml

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["merges"])


# ══════════════════════════════════════════════════════════════
# 辅助：从选中的章节构建合并 YAML
# ══════════════════════════════════════════════════════════════

def _build_merged_yaml(novel_id: int, script_id: int, chapter_numbers: list) -> dict:
    """从选中的章节收集场景并合并为完整 YAML。
    返回 {"yaml": str, "characters": int, "scenes": int, "chapters_used": int, "skipped": list}
    """
    all_scenes = []
    skipped = []

    for cn in chapter_numbers:
        cn = float(cn)
        chapters = script_repo.get_chapter_scenes(novel_id, cn, script_id=script_id)
        yaml_str = None
        for ch in chapters:
            if ch.get("yaml_content"):
                yaml_str = ch["yaml_content"]
                break
        if not yaml_str:
            skipped.append(cn)
            continue

        try:
            ch_data = yaml.safe_load(yaml_str)
            if isinstance(ch_data, dict):
                scenes = ch_data.get("scenes", [])
                for s in scenes:
                    s["source_chapter"] = cn
                    s["_chapter_num"] = cn
                all_scenes.extend(scenes)
        except Exception as e:
            logger.warning(f"[Merge] 解析第{cn}章 YAML 失败: {e}")
            skipped.append(cn)

    if not all_scenes:
        return {"yaml": "", "characters": 0, "scenes": 0, "chapters_used": 0, "skipped": skipped}

    # 提取人物
    chapters_for_extract = novel_repo.get_chapters_with_content(novel_id)
    characters = extract_characters(chapters_for_extract, novel_id)

    # 合并
    final_script = merge(characters, all_scenes)
    novel = novel_repo.get_novel(novel_id)
    final_script["meta"]["title"] = novel.get("title", "（未命名）") if novel else "（未命名）"
    final_script["meta"]["original_author"] = novel.get("author", "（未知）") if novel else "（未知）"

    yaml_str = dump_yaml(final_script)

    return {
        "yaml": yaml_str,
        "characters": len(final_script.get("characters", [])),
        "scenes": len(final_script.get("scenes", [])),
        "acts": len(final_script.get("acts", [])),
        "chapters_used": len(chapter_numbers) - len(skipped),
        "skipped": skipped,
    }


# ══════════════════════════════════════════════════════════════
# API 端点
# ══════════════════════════════════════════════════════════════

@router.get("/scripts/{script_id}/merges")
async def list_merges(script_id: int):
    """列出剧本的所有合并剧本"""
    merges = merge_repo.list_by_script(script_id)
    return {"status": "ok", "merges": merges}


@router.post("/scripts/{script_id}/merges")
async def create_merge(script_id: int, req: dict):
    """创建合并剧本"""
    chapter_numbers = req.get("chapter_numbers", [])
    if not chapter_numbers:
        return JSONResponse({"status": "error", "message": "请选择至少一个章节"}, status_code=400)

    title = req.get("title", "（未命名）").strip() or "（未命名）"
    note = req.get("note", "").strip()

    script = script_repo.get_script(script_id)
    if not script:
        return JSONResponse({"status": "error", "message": "剧本不存在"}, status_code=404)

    novel_id = script["novel_id"]

    # 构建合并 YAML
    result = await asyncio.to_thread(_build_merged_yaml, novel_id, script_id, chapter_numbers)

    if not result["yaml"]:
        all_skipped = len(result["skipped"]) == len(chapter_numbers)
        return JSONResponse({
            "status": "error",
            "message": "所选章节均未转换，请先转换后再合并" if all_skipped
            else f"仅 {result['chapters_used']} 个章节有数据，{len(result['skipped'])} 个章节未转换",
            "skipped": result["skipped"],
        }, status_code=400)

    # 保存合并剧本
    merge_id = merge_repo.create(
        script_id=script_id,
        novel_id=novel_id,
        title=title,
        note=note,
        yaml_content=result["yaml"],
        character_count=result["characters"],
        scene_count=result["scenes"],
    )

    # 保存 items（引用 script_chapter_id）
    items = []
    for cn in chapter_numbers:
        cn = float(cn)
        if cn in result["skipped"]:
            continue
        chapters = script_repo.get_chapter_scenes(novel_id, cn, script_id=script_id)
        for ch in chapters:
            if ch.get("yaml_content"):
                items.append({"script_chapter_id": ch["id"], "chapter_number": cn})
                break

    if items:
        merge_repo.add_items(merge_id, items)

    return {
        "status": "ok",
        "merge_id": merge_id,
        "message": f"合并完成：{result['chapters_used']}章 · {result['scenes']}场景 · {result['characters']}人",
        "skipped": result["skipped"],
        "yaml": result["yaml"],
        "stats": {
            "chapters": result["chapters_used"],
            "characters": result["characters"],
            "scenes": result["scenes"],
            "acts": result.get("acts", 0),
        },
    }


@router.get("/merges/{merge_id}")
async def get_merge(merge_id: int):
    """获取合并剧本详情（动态构建 YAML 确保最新）"""
    ms = merge_repo.get(merge_id)
    if not ms:
        return JSONResponse({"status": "error", "message": "合并剧本不存在"}, status_code=404)

    # 从 items 动态重建 YAML
    items = ms.get("items", [])
    if items:
        chapter_numbers = [it["chapter_number"] for it in items]
        result = await asyncio.to_thread(
            _build_merged_yaml, ms["novel_id"], ms["script_id"], chapter_numbers)
        if result["yaml"]:
            ms["yaml_content"] = result["yaml"]
            ms["stats"] = {
                "characters": result["characters"],
                "scenes": result["scenes"],
                "acts": result.get("acts", 0),
            }

    return {"status": "ok", "merge": ms}


@router.put("/merges/{merge_id}")
async def update_merge(merge_id: int, req: dict):
    """更新合并剧本的标题/备注"""
    title = req.get("title")
    note = req.get("note")
    ok = merge_repo.update(merge_id, title=title, note=note)
    if not ok:
        return JSONResponse({"status": "error", "message": "更新失败"}, status_code=500)
    return {"status": "ok", "message": "已更新"}


@router.delete("/merges/{merge_id}")
async def delete_merge(merge_id: int):
    """删除合并剧本"""
    ok = merge_repo.delete(merge_id)
    if ok is None:
        return JSONResponse({"status": "error", "message": "合并剧本不存在"}, status_code=404)
    if not ok:
        return JSONResponse({"status": "error", "message": "删除失败"}, status_code=500)
    return {"status": "ok", "message": "已删除"}
