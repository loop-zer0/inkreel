"""合并剧本数据访问"""

import json
import logging
from typing import Optional, List
from app.database import get_db

logger = logging.getLogger(__name__)


# ── MergedScript ──

def create(script_id: int, novel_id: int, title: str, note: str,
           yaml_content: str, character_count: int, scene_count: int) -> int:
    """创建合并剧本，返回 id"""
    db = get_db()
    try:
        cur = db.execute(
            """INSERT INTO merged_scripts (script_id, novel_id, title, note,
               yaml_content, character_count, scene_count)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (script_id, novel_id, title, note, yaml_content, character_count, scene_count),
        )
        db.commit()
        return cur.lastrowid
    except Exception as e:
        db.rollback()
        logger.error(f"[MergedScript] 创建失败: {e}")
        raise
    finally:
        db.close()


def list_by_script(script_id: int) -> List[dict]:
    """列出某个剧本的所有合并剧本"""
    db = get_db()
    try:
        rows = db.execute(
            "SELECT * FROM merged_scripts WHERE script_id = ? ORDER BY created_at DESC",
            (script_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        db.close()


def get(merge_id: int) -> Optional[dict]:
    """获取合并剧本详情（含 items）"""
    db = get_db()
    try:
        ms = db.execute("SELECT * FROM merged_scripts WHERE id = ?", (merge_id,)).fetchone()
        if not ms:
            return None
        ms = dict(ms)
        items = db.execute(
            """SELECT msi.*, sc.yaml_content AS chapter_yaml, sc.scene_count
               FROM merged_script_items msi
               JOIN script_chapters sc ON sc.id = msi.script_chapter_id
               WHERE msi.merged_script_id = ?
               ORDER BY msi.sort_order""",
            (merge_id,),
        ).fetchall()
        ms["items"] = [dict(it) for it in items]
        return ms
    finally:
        db.close()


def update(merge_id: int, title: str = None, note: str = None) -> bool:
    """更新标题/备注"""
    if title is None and note is None:
        return False
    db = get_db()
    try:
        sets = []
        params = []
        if title is not None:
            sets.append("title = ?")
            params.append(title)
        if note is not None:
            sets.append("note = ?")
            params.append(note)
        sets.append("updated_at = datetime('now','localtime')")
        params.append(merge_id)
        db.execute(f"UPDATE merged_scripts SET {', '.join(sets)} WHERE id = ?", params)
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"[MergedScript] 更新失败: {e}")
        return False
    finally:
        db.close()


def update_yaml(merge_id: int, yaml_content: str, character_count: int,
                scene_count: int) -> bool:
    """更新缓存的合并 YAML"""
    db = get_db()
    try:
        db.execute(
            """UPDATE merged_scripts SET yaml_content = ?, character_count = ?,
               scene_count = ?, updated_at = datetime('now','localtime')
               WHERE id = ?""",
            (yaml_content, character_count, scene_count, merge_id),
        )
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"[MergedScript] 更新 YAML 失败: {e}")
        return False
    finally:
        db.close()


def delete(merge_id: int):
    """删除合并剧本；不存在返回 None"""
    db = get_db()
    try:
        cur = db.execute("DELETE FROM merged_scripts WHERE id = ?", (merge_id,))
        if cur.rowcount == 0:
            return None
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"[MergedScript] 删除失败: {e}")
        return False
    finally:
        db.close()


# ── MergedScriptItem ──

def add_items(merge_id: int, items: List[dict]):
    """批量添加合并项。items = [{'script_chapter_id': int, 'chapter_number': float}, ...]"""
    db = get_db()
    try:
        for i, it in enumerate(items):
            db.execute(
                """INSERT INTO merged_script_items (merged_script_id, script_chapter_id,
                   chapter_number, sort_order)
                   VALUES (?, ?, ?, ?)""",
                (merge_id, it["script_chapter_id"], it["chapter_number"], i),
            )
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"[MergedScript] 添加 items 失败: {e}")
        raise
    finally:
        db.close()


def replace_items(merge_id: int, items: List[dict]):
    """替换合并项（先删后加）"""
    db = get_db()
    try:
        db.execute("DELETE FROM merged_script_items WHERE merged_script_id = ?", (merge_id,))
        for i, it in enumerate(items):
            db.execute(
                """INSERT INTO merged_script_items (merged_script_id, script_chapter_id,
                   chapter_number, sort_order)
                   VALUES (?, ?, ?, ?)""",
                (merge_id, it["script_chapter_id"], it["chapter_number"], i),
            )
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"[MergedScript] 替换 items 失败: {e}")
        raise
    finally:
        db.close()
