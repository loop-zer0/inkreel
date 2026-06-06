"""小说 + 章节数据访问"""

import logging
from typing import Optional, List
from app.database import get_db

logger = logging.getLogger(__name__)


# ── Novel ──

def save_novel(title: str, author: str, genre: str, filename: str,
               file_format: str, text: str, chapters: List[dict]) -> int:
    """保存小说及其章节，返回 novel_id"""
    db = get_db()
    try:
        cur = db.execute(
            """INSERT INTO novels (title, author, genre, filename, file_format,
               total_chars, chapter_count, original_text)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (title, author, genre, filename, file_format,
             len(text), len(chapters), text),
        )
        novel_id = cur.lastrowid

        for i, ch in enumerate(chapters):
            db.execute(
                """INSERT INTO novel_chapters (novel_id, chapter_number, sort_order,
                   title, content, char_count)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (novel_id, ch["number"], i, ch["title"],
                 ch["content"], ch.get("char_count", len(ch["content"]))),
            )

        db.commit()
        logger.info(f"[NovelRepo] 小说已保存: id={novel_id}, '{title}', {len(chapters)}章")
        return novel_id
    except Exception as e:
        db.rollback()
        logger.error(f"[NovelRepo] 保存小说失败: {e}")
        raise
    finally:
        db.close()


def list_novels() -> List[dict]:
    """列出仓库中所有小说（含剧本章节范围）"""
    db = get_db()
    try:
        rows = db.execute(
            """SELECT n.*,
                  (SELECT COUNT(*) FROM scripts WHERE novel_id = n.id) AS script_count
               FROM novels n ORDER BY n.updated_at DESC"""
        ).fetchall()
        novels = []
        for r in rows:
            novel = dict(r)
            # 获取每个剧本的章节范围
            script_summaries = db.execute(
                """SELECT s.id, s.status, s.scene_count, s.created_at,
                          MIN(sc.chapter_number) as ch_min,
                          MAX(sc.chapter_number) as ch_max,
                          COUNT(DISTINCT sc.chapter_number) as ch_count
                   FROM scripts s
                   LEFT JOIN script_chapters sc ON sc.script_id = s.id
                   WHERE s.novel_id = ?
                   GROUP BY s.id
                   ORDER BY s.created_at DESC""",
                (novel["id"],),
            ).fetchall()
            novel["script_summaries"] = [dict(s) for s in script_summaries]
            novels.append(novel)
        return novels
    finally:
        db.close()


def get_novel(novel_id: int) -> Optional[dict]:
    """获取小说详情（含章节和剧本），不返回原文和章节正文以减少传输"""
    db = get_db()
    try:
        novel = db.execute(
            """SELECT id, title, author, genre, filename, file_format,
                      total_chars, chapter_count, created_at, updated_at
               FROM novels WHERE id = ?""",
            (novel_id,),
        ).fetchone()
        if not novel:
            return None
        novel = dict(novel)

        # 章节仅返回元信息，不含 content（正文按需单独加载）
        chapters = db.execute(
            """SELECT id, novel_id, chapter_number, sort_order, title, char_count
               FROM novel_chapters WHERE novel_id = ? ORDER BY sort_order""",
            (novel_id,),
        ).fetchall()
        novel["chapters"] = [dict(c) for c in chapters]

        scripts = db.execute(
            """SELECT id, novel_id, title, status, character_count, scene_count,
                      created_at, updated_at, yaml_content
               FROM scripts WHERE novel_id = ? ORDER BY updated_at DESC""",
            (novel_id,),
        ).fetchall()
        novel["scripts"] = []
        for s in scripts:
            s = dict(s)
            # 逐章数据仅返回元信息，不含 yaml_content
            sc_rows = db.execute(
                """SELECT id, script_id, novel_id, chapter_number, scene_count, created_at
                   FROM script_chapters WHERE script_id = ? ORDER BY chapter_number""",
                (s["id"],),
            ).fetchall()
            s["chapters"] = [dict(r) for r in sc_rows]
            novel["scripts"].append(s)

        return novel
    finally:
        db.close()


def delete_novel(novel_id: int) -> bool:
    """删除小说及关联数据"""
    db = get_db()
    try:
        db.execute("DELETE FROM novels WHERE id = ?", (novel_id,))
        db.commit()
        logger.info(f"[NovelRepo] 小说已删除: id={novel_id}")
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"[NovelRepo] 删除小说失败: {e}")
        return False
    finally:
        db.close()


def touch_novel(novel_id: int):
    """更新小说的 updated_at"""
    db = get_db()
    try:
        db.execute(
            "UPDATE novels SET updated_at=datetime('now','localtime') WHERE id=?",
            (novel_id,),
        )
        db.commit()
    finally:
        db.close()


# ── Chapter ──

def get_chapter_info(novel_id: int, chapter_number: float) -> Optional[dict]:
    """获取单章元信息"""
    db = get_db()
    try:
        row = db.execute(
            "SELECT * FROM novel_chapters WHERE novel_id = ? AND chapter_number = ?",
            (novel_id, chapter_number),
        ).fetchone()
        return dict(row) if row else None
    finally:
        db.close()
