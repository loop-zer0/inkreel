"""章节分割与文本预处理"""

import re
import logging
from config import CHAPTER_PATTERNS

logger = logging.getLogger(__name__)


def split_chapters(text: str) -> list[dict]:
    """将小说全文按章节分割。

    返回: [{"number": 1, "title": "第一章 离别", "content": "..."}, ...]
    每个 chapter 的 content 是去除标题后的正文。
    """
    # 构建联合正则
    combined = "|".join(f"({p})" for p in CHAPTER_PATTERNS)
    matches = list(re.finditer(combined, text))

    if len(matches) < 3:
        logger.warning(f"仅检测到 {len(matches)} 个章节标题，可能格式不标准")

    chapters = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)

        title = m.group(0).strip()
        content = text[start:end].strip()

        # 清理章节内多余空行
        content = re.sub(r'\n{3,}', '\n\n', content)

        if len(content) < 50:
            logger.warning(f"章节 '{title}' 内容过短 ({len(content)} 字)，跳过")
            continue

        chapters.append({
            "number": i + 1,
            "title": title,
            "content": content,
            "char_count": len(content),
        })

    return chapters


def detect_chapter_format(text: str) -> str:
    """检测小说使用的章节格式，用于提示用户"""
    for pattern in CHAPTER_PATTERNS:
        m = re.search(pattern, text)
        if m:
            return m.group(0)
    return "未检测到标准章节格式"


def segment_long_chapter(content: str, max_chars: int = 3000) -> list[str]:
    """将超长章节按段落边界切分为多个片段，每段尽量在 max_chars 以内"""
    if len(content) <= max_chars:
        return [content]

    segments = []
    paragraphs = content.split('\n')
    current = ""

    for para in paragraphs:
        if len(current) + len(para) > max_chars and current:
            segments.append(current.strip())
            current = para
        else:
            if current:
                current += '\n' + para
            else:
                current = para

    if current.strip():
        segments.append(current.strip())

    logger.info(f"  章节分段: {len(content)} 字 → {len(segments)} 段")
    return segments
