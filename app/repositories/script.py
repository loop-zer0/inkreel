"""剧本 + 逐章场景数据访问"""

import logging
from typing import Optional, List
from app.database import get_db

logger = logging.getLogger(__name__)


# ── Script ──

def save_script(novel_id: int, title: str, yaml_content: str,
                character_count: int, scene_count: int,
                status: str = "complete") -> int:
    """保存完整剧本，返回 script_id"""
    db = get_db()
    try:
        cur = db.execute(
            """INSERT INTO scripts (novel_id, title, status, yaml_content,
               character_count, scene_count)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (novel_id, title, status, yaml_content, character_count, scene_count),
        )
        script_id = cur.lastrowid
        db.execute(
            "UPDATE novels SET updated_at = datetime('now','localtime') WHERE id = ?",
            (novel_id,),
        )
        db.commit()
        logger.info(f"[ScriptRepo] 剧本已保存: id={script_id}, '{title}'")
        return script_id
    except Exception as e:
        db.rollback()
        logger.error(f"[ScriptRepo] 保存剧本失败: {e}")
        raise
    finally:
        db.close()


def get_script(script_id: int) -> Optional[dict]:
    """获取完整剧本（含逐章数据）"""
    db = get_db()
    try:
        script = db.execute("SELECT * FROM scripts WHERE id = ?", (script_id,)).fetchone()
        if not script:
            return None
        script = dict(script)
        chapters = db.execute(
            "SELECT * FROM script_chapters WHERE script_id = ? ORDER BY chapter_number",
            (script_id,),
        ).fetchall()
        script["chapters"] = [dict(c) for c in chapters]
        return script
    finally:
        db.close()


def update_script(script_id: int, yaml_content: str = None,
                  title: str = None, status: str = None) -> bool:
    """更新剧本的 YAML / 标题 / 状态（外部手动编辑入口，会标记 manually_edited）"""
    db = get_db()
    try:
        sets = []
        params = []
        if yaml_content is not None:
            sets.append("yaml_content = ?")
            params.append(yaml_content)
            sets.append("manually_edited = 1")
        if title is not None:
            sets.append("title = ?")
            params.append(title)
        if status is not None:
            sets.append("status = ?")
            params.append(status)
        if not sets:
            return False
        sets.append("updated_at = datetime('now','localtime')")
        params.append(script_id)
        db.execute(f"UPDATE scripts SET {', '.join(sets)} WHERE id = ?", params)
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"[ScriptRepo] 更新剧本失败: {e}")
        return False
    finally:
        db.close()


def get_or_create_draft_script(novel_id: int, title: str = "（未命名）") -> dict:
    """获取小说的草稿剧本，没有则创建（永远不返回已完成的剧本）"""
    db = get_db()
    try:
        script = db.execute(
            """SELECT * FROM scripts WHERE novel_id = ? AND status = 'draft'
               ORDER BY id DESC LIMIT 1""",
            (novel_id,),
        ).fetchone()
        if not script:
            cur = db.execute(
                """INSERT INTO scripts (novel_id, title, status, yaml_content,
                   character_count, scene_count)
                   VALUES (?, ?, 'draft', '', 0, 0)""",
                (novel_id, title),
            )
            db.commit()
            script = db.execute("SELECT * FROM scripts WHERE id = ?", (cur.lastrowid,)).fetchone()

        # 清理多余空草稿（保留当前使用的这一个）
        db.execute(
            """DELETE FROM scripts WHERE novel_id = ? AND status = 'draft'
               AND id != ?
               AND NOT EXISTS (SELECT 1 FROM script_chapters WHERE script_id = scripts.id)""",
            (novel_id, script["id"]),
        )
        db.commit()

        script = dict(script)
        chapters = db.execute(
            "SELECT * FROM script_chapters WHERE script_id = ? ORDER BY chapter_number",
            (script["id"],),
        ).fetchall()
        script["chapters"] = [dict(c) for c in chapters]
        return script
    finally:
        db.close()


def finalize_script(script_id: int, yaml_content: str,
                    character_count: int, scene_count: int) -> bool:
    """将草稿剧本标记为完成"""
    db = get_db()
    try:
        db.execute(
            """UPDATE scripts SET status = 'complete', yaml_content = ?,
               character_count = ?, scene_count = ?,
               updated_at = datetime('now','localtime')
               WHERE id = ?""",
            (yaml_content, character_count, scene_count, script_id),
        )
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"[ScriptRepo] 完成剧本失败: {e}")
        return False
    finally:
        db.close()


def list_scripts(novel_id: int = None) -> List[dict]:
    """列出剧本"""
    db = get_db()
    try:
        if novel_id:
            rows = db.execute(
                "SELECT * FROM scripts WHERE novel_id = ? ORDER BY updated_at DESC",
                (novel_id,),
            ).fetchall()
        else:
            rows = db.execute("SELECT * FROM scripts ORDER BY updated_at DESC").fetchall()
        return [dict(r) for r in rows]
    finally:
        db.close()


def delete_script(script_id: int) -> bool:
    """删除剧本；不存在返回 None 表示 404"""
    db = get_db()
    try:
        cur = db.execute("DELETE FROM scripts WHERE id = ?", (script_id,))
        if cur.rowcount == 0:
            return None
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"[ScriptRepo] 删除剧本失败: {e}")
        return False
    finally:
        db.close()


def get_empty_draft(novel_id: int) -> Optional[dict]:
    """获取小说的空草稿（无任何章节场景），没有则返回 None"""
    db = get_db()
    try:
        script = db.execute(
            """SELECT s.* FROM scripts s
               WHERE s.novel_id = ? AND s.status = 'draft'
               AND NOT EXISTS (SELECT 1 FROM script_chapters sc WHERE sc.script_id = s.id)
               ORDER BY s.id DESC LIMIT 1""",
            (novel_id,),
        ).fetchone()
        return dict(script) if script else None
    finally:
        db.close()


def create_empty_script(novel_id: int, title: str) -> int:
    """创建一个空草稿剧本，返回 script_id"""
    db = get_db()
    try:
        cur = db.execute(
            """INSERT INTO scripts (novel_id, title, status, yaml_content,
               character_count, scene_count)
               VALUES (?, ?, 'draft', '', 0, 0)""",
            (novel_id, title),
        )
        db.commit()
        return cur.lastrowid
    finally:
        db.close()


# ── Script Chapters ──

def save_script_chapter(script_id: int, novel_id: int, chapter_number: float,
                        yaml_content: str, scene_count: int) -> int:
    """保存/更新单章生成的场景 YAML"""
    db = get_db()
    try:
        db.execute(
            "DELETE FROM script_chapters WHERE script_id = ? AND chapter_number = ?",
            (script_id, chapter_number),
        )
        cur = db.execute(
            """INSERT INTO script_chapters (script_id, novel_id, chapter_number,
               yaml_content, scene_count)
               VALUES (?, ?, ?, ?, ?)""",
            (script_id, novel_id, chapter_number, yaml_content, scene_count),
        )
        db.commit()
        return cur.lastrowid
    except Exception as e:
        db.rollback()
        logger.error(f"[ScriptRepo] 保存章场景失败: {e}")
        raise
    finally:
        db.close()


def get_chapter_scenes(novel_id: int, chapter_number: float,
                       script_id: int = None) -> List[dict]:
    """获取某章已生成的场景数据"""
    db = get_db()
    try:
        if script_id:
            rows = db.execute(
                """SELECT * FROM script_chapters
                   WHERE novel_id = ? AND chapter_number = ? AND script_id = ?
                   ORDER BY chapter_number""",
                (novel_id, chapter_number, script_id),
            ).fetchall()
        else:
            rows = db.execute(
                """SELECT * FROM script_chapters
                   WHERE novel_id = ? AND chapter_number = ?
                   ORDER BY chapter_number""",
                (novel_id, chapter_number),
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        db.close()


def get_generated_chapter_numbers(novel_id: int, script_id: int = None) -> List[float]:
    """获取已生成场景的章节号列表（可指定剧本）"""
    db = get_db()
    try:
        if script_id:
            rows = db.execute(
                "SELECT DISTINCT chapter_number FROM script_chapters WHERE novel_id = ? AND script_id = ? ORDER BY chapter_number",
                (novel_id, script_id),
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT DISTINCT chapter_number FROM script_chapters WHERE novel_id = ? ORDER BY chapter_number",
                (novel_id,),
            ).fetchall()
        return [r["chapter_number"] for r in rows]
    except Exception:
        return []
    finally:
        db.close()


def is_manually_edited(script_id: int) -> bool:
    """检查剧本是否被手动编辑过"""
    db = get_db()
    try:
        row = db.execute(
            "SELECT manually_edited FROM scripts WHERE id = ?", (script_id,)
        ).fetchone()
        return bool(row and row["manually_edited"])
    finally:
        db.close()


def auto_save_yaml(script_id: int, yaml_content: str,
                   character_count: int, scene_count: int) -> bool:
    """自动合并保存 YAML——不标记 manually_edited，覆盖草稿的 yaml_content"""
    db = get_db()
    try:
        db.execute(
            """UPDATE scripts SET yaml_content = ?, character_count = ?, scene_count = ?,
               updated_at = datetime('now','localtime')
               WHERE id = ?""",
            (yaml_content, character_count, scene_count, script_id),
        )
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"[ScriptRepo] 自动保存 YAML 失败: {e}")
        return False
    finally:
        db.close()


def reset_manual_edit(script_id: int) -> bool:
    """重置 manually_edited 标记（用户选择恢复自动合并时调用）"""
    db = get_db()
    try:
        db.execute("UPDATE scripts SET manually_edited = 0 WHERE id = ?", (script_id,))
        db.commit()
        return True
    finally:
        db.close()
