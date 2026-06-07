"""翻译数据访问"""

import logging
from typing import Optional, List
from app.database import get_db

logger = logging.getLogger(__name__)


def create(target_type: str, target_id: int, language: str, language_label: str,
           translated_yaml: str) -> int:
    """创建翻译记录，返回 id"""
    db = get_db()
    try:
        cur = db.execute(
            """INSERT INTO translations (target_type, target_id, language, language_label, translated_yaml)
               VALUES (?, ?, ?, ?, ?)""",
            (target_type, target_id, language, language_label, translated_yaml),
        )
        db.commit()
        return cur.lastrowid
    except Exception as e:
        db.rollback()
        logger.error(f"[Translation] 创建失败: {e}")
        raise
    finally:
        db.close()


def get(translation_id: int) -> Optional[dict]:
    """获取单条翻译"""
    db = get_db()
    try:
        row = db.execute("SELECT * FROM translations WHERE id = ?", (translation_id,)).fetchone()
        return dict(row) if row else None
    finally:
        db.close()


def list_by_target(target_type: str, target_id: int) -> List[dict]:
    """列出某个目标的所有翻译"""
    db = get_db()
    try:
        rows = db.execute(
            "SELECT * FROM translations WHERE target_type = ? AND target_id = ? ORDER BY created_at DESC",
            (target_type, target_id),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        db.close()


def delete(translation_id: int):
    """删除翻译；不存在返回 None"""
    db = get_db()
    try:
        cur = db.execute("DELETE FROM translations WHERE id = ?", (translation_id,))
        if cur.rowcount == 0:
            return None
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"[Translation] 删除失败: {e}")
        return False
    finally:
        db.close()
