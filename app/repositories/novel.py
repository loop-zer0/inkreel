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
    """删除小说及关联数据；不存在返回 None 表示 404"""
    db = get_db()
    try:
        cur = db.execute("DELETE FROM novels WHERE id = ?", (novel_id,))
        if cur.rowcount == 0:
            return None  # 资源不存在
        db.commit()
        logger.info(f"[NovelRepo] 小说已删除: id={novel_id}")
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"[NovelRepo] 删除小说失败: {e}")
        return False
    finally:
        db.close()


def update_novel(novel_id: int, title: str = None, author: str = None, genre: str = None) -> bool:
    """更新小说元信息"""
    db = get_db()
    try:
        fields = []
        values = []
        if title is not None:
            fields.append("title = ?")
            values.append(title)
        if author is not None:
            fields.append("author = ?")
            values.append(author)
        if genre is not None:
            fields.append("genre = ?")
            values.append(genre)
        if not fields:
            return False
        fields.append("updated_at = datetime('now','localtime')")
        values.append(novel_id)
        db.execute(f"UPDATE novels SET {', '.join(fields)} WHERE id = ?", values)
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"[NovelRepo] 更新小说失败: {e}")
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
    """获取单章元信息（含内容）"""
    db = get_db()
    try:
        row = db.execute(
            "SELECT * FROM novel_chapters WHERE novel_id = ? AND chapter_number = ?",
            (novel_id, chapter_number),
        ).fetchone()
        return dict(row) if row else None
    finally:
        db.close()


def get_chapter_by_id(chapter_id: int) -> Optional[dict]:
    """按 ID 获取章节"""
    db = get_db()
    try:
        row = db.execute("SELECT * FROM novel_chapters WHERE id = ?", (chapter_id,)).fetchone()
        return dict(row) if row else None
    finally:
        db.close()


def get_chapters_with_content(novel_id: int) -> List[dict]:
    """获取小说的所有章节（含正文），供人物提取使用"""
    db = get_db()
    try:
        rows = db.execute(
            "SELECT * FROM novel_chapters WHERE novel_id = ? ORDER BY sort_order",
            (novel_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        db.close()


def update_chapter(chapter_id: int, title: str = None, content: str = None) -> bool:
    """更新章节标题和/或内容"""
    if title is None and content is None:
        return False
    db = get_db()
    try:
        sets = []
        params = []
        if title is not None:
            sets.append("title = ?")
            params.append(title)
        if content is not None:
            sets.append("content = ?")
            params.append(content)
            sets.append("char_count = ?")
            params.append(len(content))
        params.append(chapter_id)
        db.execute(f"UPDATE novel_chapters SET {', '.join(sets)} WHERE id = ?", params)
        db.commit()
        # 更新小说的 updated_at
        row = db.execute("SELECT novel_id FROM novel_chapters WHERE id = ?", (chapter_id,)).fetchone()
        if row:
            db.execute("UPDATE novels SET updated_at = datetime('now','localtime') WHERE id = ?", (row["novel_id"],))
            db.commit()
        return True
    except Exception as e:
        db.rollback()
        return False
    finally:
        db.close()


def delete_chapter(chapter_id: int) -> Optional[int]:
    """删除单章，返回 novel_id 以便前端刷新。不存在返回 None"""
    db = get_db()
    try:
        row = db.execute("SELECT novel_id FROM novel_chapters WHERE id = ?", (chapter_id,)).fetchone()
        if not row:
            return None
        nid = row["novel_id"]
        db.execute("DELETE FROM novel_chapters WHERE id = ?", (chapter_id,))
        # 更新小说的章节数
        actual_count = db.execute(
            "SELECT COUNT(*) as cnt FROM novel_chapters WHERE novel_id = ?", (nid,)
        ).fetchone()["cnt"]
        db.execute(
            "UPDATE novels SET chapter_count = ?, updated_at = datetime('now','localtime') WHERE id = ?",
            (actual_count, nid),
        )
        db.commit()
        logger.info(f"[NovelRepo] 章节已删除: id={chapter_id}, novel={nid}, remaining={actual_count}")
        return nid
    except Exception as e:
        db.rollback()
        logger.error(f"[NovelRepo] 删除章节失败: {e}")
        return None
    finally:
        db.close()


def append_chapters(novel_id: int, chapters: List[dict]) -> dict:
    """追加新章节。跳过已存在的章节号，返回 {added: int, skipped: int}"""
    db = get_db()
    try:
        # 获取已有章节号
        existing = {
            r["chapter_number"]
            for r in db.execute(
                "SELECT chapter_number FROM novel_chapters WHERE novel_id = ?", (novel_id,)
            ).fetchall()
        }
        # 获取当前最大 sort_order
        max_sort = db.execute(
            "SELECT COALESCE(MAX(sort_order), -1) + 1 AS n FROM novel_chapters WHERE novel_id = ?",
            (novel_id,),
        ).fetchone()["n"]

        added = 0
        skipped = 0
        for ch in chapters:
            cn = ch.get("number", ch.get("num", 0))
            if cn in existing:
                skipped += 1
                continue
            db.execute(
                """INSERT INTO novel_chapters (novel_id, chapter_number, sort_order, title, content, char_count)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (novel_id, cn, max_sort + added, ch.get("title", ""), ch.get("content", ""), len(ch.get("content", ""))),
            )
            added += 1

        if added > 0:
            db.execute(
                "UPDATE novels SET chapter_count = chapter_count + ?, updated_at = datetime('now','localtime') WHERE id = ?",
                (added, novel_id),
            )
        db.commit()
        logger.info(f"[NovelRepo] 追加章节: novel={novel_id}, +{added}, 跳过{skipped}")
        return {"added": added, "skipped": skipped}
    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()


def bulk_add_chapters(novel_id: int, chapters: List[dict]) -> int:
    """批量插入新章节（不做去重，调用方已筛选）。返回插入数量"""
    db = get_db()
    try:
        max_sort = db.execute(
            "SELECT COALESCE(MAX(sort_order), -1) + 1 AS n FROM novel_chapters WHERE novel_id = ?",
            (novel_id,),
        ).fetchone()["n"]

        added = 0
        for ch in chapters:
            cn = ch.get("chapter_number", ch.get("number", 0))
            db.execute(
                """INSERT INTO novel_chapters (novel_id, chapter_number, sort_order, title, content, char_count)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (novel_id, cn, max_sort + added, ch.get("title", ""), ch.get("content", ""), len(ch.get("content", ""))),
            )
            added += 1

        if added > 0:
            db.execute(
                "UPDATE novels SET chapter_count = chapter_count + ?, updated_at = datetime('now','localtime') WHERE id = ?",
                (added, novel_id),
            )
        db.commit()
        return added
    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()


def bulk_update_chapters(novel_id: int, chapters: List[dict]) -> int:
    """批量更新已有章节的内容（按 novel_id + chapter_number 匹配）。返回更新数量"""
    db = get_db()
    try:
        updated = 0
        for ch in chapters:
            cn = ch.get("chapter_number", ch.get("number", 0))
            content = ch.get("content", "")
            title = ch.get("title")
            cur = db.execute(
                """UPDATE novel_chapters SET content = ?, char_count = ?"""
                + (", title = ?" if title else "") +
                """ WHERE novel_id = ? AND chapter_number = ?""",
                [content, len(content)] + ([title] if title else []) + [novel_id, cn],
            )
            updated += cur.rowcount
        if updated > 0:
            db.execute(
                "UPDATE novels SET updated_at = datetime('now','localtime') WHERE id = ?",
                (novel_id,),
            )
        db.commit()
        return updated
    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()
