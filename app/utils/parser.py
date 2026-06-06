"""章节分割与文本预处理"""

import re
import logging
from typing import List, Optional
from app.config import CHAPTER_PATTERNS

logger = logging.getLogger(__name__)

# ── 中文数字映射 ──
_CHINESE_DIGITS = {'零': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9}
_CHINESE_UNITS = {'十': 10, '百': 100, '千': 1000}

_ROMAN_NUM_MAP = {
    'I': 1, 'II': 2, 'III': 3, 'IV': 4, 'V': 5,
    'VI': 6, 'VII': 7, 'VIII': 8, 'IX': 9, 'X': 10,
    'XI': 11, 'XII': 12, 'XIII': 13, 'XIV': 14, 'XV': 15,
    'XVI': 16, 'XVII': 17, 'XVIII': 18, 'XIX': 19, 'XX': 20,
    'XXI': 21, 'XXII': 22, 'XXIII': 23, 'XXIV': 24, 'XXV': 25,
    'XXVI': 26, 'XXVII': 27, 'XXVIII': 28, 'XXIX': 29, 'XXX': 30,
    'XXXI': 31, 'XXXII': 32, 'XXXIII': 33, 'XXXIV': 34, 'XXXV': 35,
    'XXXVI': 36, 'XXXVII': 37, 'XXXVIII': 38, 'XXXIX': 39, 'XL': 40,
    'XLI': 41, 'XLII': 42, 'XLIII': 43, 'XLIV': 44, 'XLV': 45,
    'XLVI': 46, 'XLVII': 47, 'XLVIII': 48, 'XLIX': 49, 'L': 50,
}


def chinese_to_int(cn: str) -> Optional[int]:
    """中文数字 → 整数，如 '三十八' → 38"""
    if not cn:
        return None
    if cn.isdigit():
        return int(cn)
    result = 0
    current = 0
    for ch in cn:
        if ch in _CHINESE_DIGITS:
            current = _CHINESE_DIGITS[ch]
        elif ch in _CHINESE_UNITS:
            unit = _CHINESE_UNITS[ch]
            if current == 0:
                current = 1
            result += current * unit
            current = 0
        else:
            return None
    result += current
    return result if result > 0 else None


def roman_to_int(roman: str) -> int:
    """罗马数字 → 整数"""
    return _ROMAN_NUM_MAP.get(roman.upper().rstrip('.'), 0)


def parse_chapter_number(title: str) -> float:
    """从章节标题中提取数字序号"""
    m = re.search(r'(\d+(?:\.\d+)?)', title)
    if m:
        return float(m.group(1))
    m = re.search(r'\b([IVX]+)\.?', title, re.IGNORECASE)
    if m:
        val = roman_to_int(m.group(1))
        if val > 0:
            return float(val)
    m = re.search(r'第([零一二三四五六七八九十百千]+)', title)
    if m:
        val = chinese_to_int(m.group(1))
        if val is not None:
            return float(val)
    return 0.0


def split_chapters(text: str) -> List[dict]:
    """将小说全文按章节分割"""
    combined = "|".join(f"({p})" for p in CHAPTER_PATTERNS)
    matches = list(re.finditer(combined, text))

    if len(matches) < 3:
        logger.warning(f"仅检测到 {len(matches)} 个章节标题")

    chapters = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        title = m.group(0).strip()
        content = text[start:end].strip()
        content = re.sub(r'\n{3,}', '\n\n', content)

        if len(content) < 50:
            logger.warning(f"章节 '{title}' 内容过短 ({len(content)} 字)，跳过")
            continue

        chapters.append({
            "number": i + 1,
            "title": title,
            "content": content,
            "char_count": len(content),
            "parsed_number": parse_chapter_number(title),
        })

    chapters = sorted(chapters, key=lambda c: c.get("parsed_number") or 0)
    for i, ch in enumerate(chapters):
        ch["number"] = ch.get("parsed_number") or (i + 1)

    return chapters


def detect_chapter_format(text: str) -> str:
    """检测章节格式"""
    for pattern in CHAPTER_PATTERNS:
        m = re.search(pattern, text)
        if m:
            return m.group(0)
    return "未检测到标准章节格式"


def segment_long_chapter(content: str, max_chars: int = 3000) -> list[str]:
    """将超长章节按段落边界切分"""
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
            current = (current + '\n' + para) if current else para

    if current.strip():
        segments.append(current.strip())

    logger.info(f"  章节分段: {len(content)} 字 → {len(segments)} 段")
    return segments
