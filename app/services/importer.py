"""导入流程 — 文件解析 → 章节检测 → 体裁检测 → 入库"""

import json
import logging
from typing import List, Tuple
from app.utils.reader import extract_text
from app.utils.parser import split_chapters, detect_chapter_format
from app.services.genre import detect as detect_genre
from app.repositories.novel import save_novel

logger = logging.getLogger(__name__)

# 支持的文件格式
SUPPORTED_FORMATS = ("txt", "text", "md", "markdown", "docx", "epub")


def preview_file(file_bytes: bytes, filename: str) -> dict:
    """预览上传文件：解析文本 → 分割章节 → 体裁检测（不入库）

    返回: {"status": "ok", "filename": ..., "total_chars": ...,
            "chapter_count": ..., "genre": ..., "chapters": [...]}
    """
    ext = _get_ext(filename)
    if ext not in SUPPORTED_FORMATS:
        return {"status": "error", "message": f"不支持 .{ext} 格式，支持: {', '.join(SUPPORTED_FORMATS)}"}

    try:
        text = extract_text(file_bytes, filename)
    except ValueError as e:
        return {"status": "error", "message": str(e)}
    except Exception as e:
        return {"status": "error", "message": f"文件解析失败: {e}"}

    text = text.strip()
    if len(text) < 200:
        return {"status": "error", "message": f"文件内容过短 ({len(text)} 字)，至少需要 200 字"}

    chapters = split_chapters(text)
    if not chapters:
        return {"status": "error", "message": "未检测到章节"}

    fmt = detect_chapter_format(text)
    genre = detect_genre(text[:1500])

    return {
        "status": "ok",
        "filename": filename,
        "total_chars": len(text),
        "chapter_count": len(chapters),
        "chapter_format": fmt,
        "genre": genre,
        "chapters": [
            {"num": c["number"], "title": c["title"], "chars": c["char_count"]}
            for c in chapters
        ],
        "_text": text,      # 内部传递，不入库
        "_chapters": chapters,
        "_ext": ext,
    }


def import_novel(title: str, author: str, filename: str,
                 text: str, chapters: List[dict], ext: str,
                 genre: str = "") -> int:
    """确认导入，将小说存入仓库。返回 novel_id"""
    if not genre:
        genre = detect_genre(text[:1500])

    return save_novel(
        title=title or filename,
        author=author or "（未知）",
        genre=genre,
        filename=filename,
        file_format=ext,
        text=text,
        chapters=chapters,
    )


def _get_ext(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
