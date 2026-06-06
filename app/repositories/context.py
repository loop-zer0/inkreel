"""上下文缓存数据访问 — 章节摘要缓存"""

import logging
from typing import Optional, List
from app.database import get_db

logger = logging.getLogger(__name__)


def save_chapter_context(novel_id: int, chapter_number: float,
                         summary: str = "", key_events: str = "",
                         characters_intro: str = "") -> bool:
    """保存章节摘要到上下文缓存"""
    db = get_db()
    try:
        db.execute(
            """INSERT OR REPLACE INTO context_cache
               (novel_id, chapter_number, summary, key_events, characters_intro)
               VALUES (?, ?, ?, ?, ?)""",
            (novel_id, chapter_number, summary, key_events, characters_intro),
        )
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"[ContextRepo] 保存失败: {e}")
        return False
    finally:
        db.close()


def get_chapter_context(novel_id: int, chapter_number: float) -> Optional[dict]:
    """获取单章上下文缓存"""
    db = get_db()
    try:
        row = db.execute(
            "SELECT * FROM context_cache WHERE novel_id = ? AND chapter_number = ?",
            (novel_id, chapter_number),
        ).fetchone()
        return dict(row) if row else None
    finally:
        db.close()


def get_all_preceding_context(novel_id: int, before_chapter: float) -> List[dict]:
    """获取指定章节之前的所有摘要"""
    db = get_db()
    try:
        rows = db.execute(
            """SELECT * FROM context_cache
               WHERE novel_id = ? AND chapter_number < ?
               ORDER BY chapter_number ASC""",
            (novel_id, before_chapter),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        db.close()


def clear_context_cache(novel_id: int) -> bool:
    """清空小说的上下文缓存"""
    db = get_db()
    try:
        db.execute("DELETE FROM context_cache WHERE novel_id = ?", (novel_id,))
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        return False
    finally:
        db.close()


def get_all_generated_summaries(novel_id: int, before_chapter: float) -> str:
    """收集前文章节摘要，拼接成上下文文本"""
    contexts = get_all_preceding_context(novel_id, before_chapter)
    if not contexts:
        return ""

    lines = ["【前文摘要】"]
    for ctx in contexts:
        ch_num = ctx["chapter_number"]
        ch_num_str = str(int(ch_num)) if ch_num == int(ch_num) else str(ch_num)
        lines.append(f"\n第{ch_num_str}章：{ctx['summary']}")
        if ctx.get("key_events"):
            lines.append(f"  关键事件：{ctx['key_events']}")

    return "\n".join(lines)
