"""剧本查看/删除路由"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.repositories import script as script_repo

router = APIRouter(prefix="/api", tags=["scripts"])


@router.get("/scripts/{script_id}")
async def get_script(script_id: int):
    """剧本详情"""
    script = script_repo.get_script(script_id)
    if not script:
        return JSONResponse({"status": "error", "message": "剧本不存在"}, status_code=404)
    return {"status": "ok", "script": script}


@router.delete("/scripts/{script_id}")
async def delete_script(script_id: int):
    """删除剧本"""
    ok = script_repo.delete_script(script_id)
    if not ok:
        return JSONResponse({"status": "error", "message": "删除失败"}, status_code=500)
    return {"status": "ok", "message": "已删除"}


@router.put("/scripts/{script_id}")
async def update_script(script_id: int, req: dict):
    """更新剧本 YAML 和标题"""
    yaml_content = req.get("yaml_content")
    title = req.get("title")
    ok = script_repo.update_script(script_id, yaml_content=yaml_content, title=title)
    if not ok:
        return JSONResponse({"status": "error", "message": "更新失败"}, status_code=500)
    return {"status": "ok", "message": "已更新"}


@router.post("/novels/{novel_id}/scripts/new")
async def create_new_script(novel_id: int, req: dict = None):
    """创建新剧本（如有空草稿则复用，避免产生无用的空剧本）"""
    title = req.get("title", "（未命名）") if req else "（未命名）"
    # 检查是否已有空草稿 → 复用
    existing = script_repo.get_empty_draft(novel_id)
    if existing:
        return {"status": "ok", "script_id": existing["id"], "message": "复用已有空草稿"}
    script_id = script_repo.create_empty_script(novel_id, title)
    return {"status": "ok", "script_id": script_id, "message": "新剧本已创建"}


@router.get("/novels/{novel_id}/chapters/{chapter_num}/yaml")
async def get_chapter_yaml(novel_id: int, chapter_num: float):
    """获取某章已生成的 YAML（轻量查询，不传全量数据）"""
    rows = script_repo.get_chapter_scenes(novel_id, chapter_num)
    if not rows:
        return JSONResponse({"status": "error", "message": "该章节暂无数据"}, status_code=404)
    # 返回最新一条有内容的
    for r in reversed(rows):
        if r.get("yaml_content"):
            return {"status": "ok", "yaml": r["yaml_content"], "chapter_number": chapter_num}
    return JSONResponse({"status": "error", "message": "该章节 YAML 为空"}, status_code=404)
