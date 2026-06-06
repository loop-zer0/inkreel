"""体裁检测 — 基于关键词的快速分类"""

import re

_KEYWORDS = {
    "武侠": ["剑", "江湖", "门派", "内力", "武林", "侠", "功法"],
    "科幻": ["飞船", "星球", "外星", "AI", "机器人", "量子", "基因"],
    "奇幻": ["魔法", "龙", "精灵", "咒语", "王国", "巫师", "魔"],
    "悬疑": ["凶手", "侦探", "尸体", "密室", "线索", "谋杀"],
    "爱情": ["爱情", "恋爱", "婚礼", "求婚", "未婚", "情侣"],
    "恐怖": ["鬼", "幽灵", "诅咒", "血", "恐怖", "噩梦"],
    "历史": ["皇帝", "将军", "战争", "朝代", "陛下", "起义"],
    "文学经典": [],
}

_CLASSIC_MARKERS = ["CHAPTER", "Mr.", "Mrs.", "Miss", "Lady", "Lord", "gentleman"]


def detect(text_sample: str) -> str:
    """快速体裁检测"""
    scores = {}
    for genre, words in _KEYWORDS.items():
        score = sum(text_sample.lower().count(w.lower()) for w in words)
        if score > 0:
            scores[genre] = score

    if scores:
        return max(scores, key=scores.get)

    classic_score = sum(text_sample.count(m) for m in _CLASSIC_MARKERS)
    if classic_score > 3:
        return "文学经典"

    return "通用"
