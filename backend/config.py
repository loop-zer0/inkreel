"""全局配置"""
import os

# 服务器
HOST = "0.0.0.0"
PORT = 8766

# ── LLM 模式：online（云端 API）/ offline（本地 Ollama）──
LLM_MODE = os.environ.get("NOVEL2SCRIPT_MODE", "online")  # online | offline

# 云端配置（DeepSeek）
ONLINE_BASE_URL = "https://api.deepseek.com"
ONLINE_API_KEY = os.environ.get("DEEPSEEK_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
ONLINE_MODEL = "deepseek-chat"

# 本地 Ollama 配置
OLLAMA_BASE_URL = "http://localhost:11434/v1"
OLLAMA_API_KEY = "ollama"  # Ollama 不需要真实 key
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")  # 默认用 qwen2.5 7B

# 运行时解析
def get_llm_config():
    """返回当前模式的 (base_url, api_key, model)"""
    if LLM_MODE == "offline":
        return OLLAMA_BASE_URL, OLLAMA_API_KEY, OLLAMA_MODEL
    return ONLINE_BASE_URL, ONLINE_API_KEY, ONLINE_MODEL

def set_llm_mode(mode: str):
    """运行时切换模式"""
    global LLM_MODE
    if mode in ("online", "offline"):
        LLM_MODE = mode

LLM_TEMPERATURE = 0.3
LLM_MAX_TOKENS = 4096

# 文件限制
MAX_FILE_SIZE_MB = 10
MAX_CHAPTER_LENGTH_CHARS = 6000  # 单章超过此长度则分段处理
CHAPTER_SEGMENT_SIZE = 3000       # 每段约 3000 字

# 章节识别正则（中英文 + 罗马数字）
CHAPTER_PATTERNS = [
    # 中文
    r'第[零一二三四五六七八九十百千\d]+章',
    r'第[零一二三四五六七八九十百千\d]+回',
    r'第[零一二三四五六七八九十百千\d]+节',
    # 英文: Chapter + 阿拉伯数字
    r'[Cc]hapter\s+\d+',
    r'CHAPTER\s+\d+',
    # 英文: Chapter + 罗马数字 (I, II, III, IV, V, VI, VII, VIII, IX, X, XI...)
    r'[Cc]hapter\s+[IVX]+\.?',
    r'CHAPTER\s+[IVX]+\.?',
    # 英文: 书信体 (Letter 1, Letter I)
    r'[Ll]etter\s+(\d+|[IVX]+)\.?',
    # 英文: 卷/部分 (Part I, Book I, Volume I)
    r'[Pp]art\s+(\d+|[IVX]+)\.?',
    r'[Bb]ook\s+(\d+|[IVX]+)\.?',
    r'[Vv]olume\s+(\d+|[IVX]+)\.?',
]
