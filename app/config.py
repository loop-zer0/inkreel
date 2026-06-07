"""应用配置 — 环境变量 + 常量"""

import os

# ── 加载 .env 文件 ──
_ENV_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
if os.path.exists(_ENV_FILE):
    with open(_ENV_FILE, "r", encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _key, _, _val = _line.partition("=")
                _key, _val = _key.strip(), _val.strip()
                if _key and _key not in os.environ:
                    os.environ[_key] = _val

# ── 服务器 ──
HOST = "0.0.0.0"
PORT = 8766

# ── 路径 ──
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_PATH = os.environ.get(
    "INKREEL_DB_PATH",
    os.path.join(_PROJECT_ROOT, "data", "inkreel.db"),
)
OUTPUT_DIR = os.path.join(_PROJECT_ROOT, "output")
FRONTEND_DIR = os.path.join(_PROJECT_ROOT, "frontend")
DOCS_DIR = os.path.join(_PROJECT_ROOT, "docs")

# ── LLM 配置 ──

def get_llm_config():
    """返回 (base_url, api_key, model)"""
    base_url = os.environ.get("INKREEL_BASE_URL", "https://token-plan-cn.xiaomimimo.com/v1")
    api_key = os.environ.get("INKREEL_API_KEY", "")
    model = os.environ.get("INKREEL_MODEL", "mimo-v2.5-pro")
    return base_url, api_key, model


# ── LLM 参数 ──
LLM_TEMPERATURE = 0.3
LLM_MAX_TOKENS = 4096

# ── 文件限制 ──
MAX_FILE_SIZE_MB = 10
MAX_CHAPTER_LENGTH_CHARS = 6000
CHAPTER_SEGMENT_SIZE = 3000

# ── 认证 ──
SECRET_KEY = os.environ.get("INKREEL_SECRET_KEY", "inkreel-secret-key-change-me")

# ── 邮件（QQ 邮箱 SMTP）──
SMTP_HOST = os.environ.get("INKREEL_SMTP_HOST", "smtp.qq.com")
SMTP_PORT = int(os.environ.get("INKREEL_SMTP_PORT", "465"))
SMTP_USER = os.environ.get("INKREEL_SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("INKREEL_SMTP_PASSWORD", "")
SMTP_FROM = os.environ.get("INKREEL_SMTP_FROM", SMTP_USER)  # 发件人，默认同 SMTP_USER

# ── 章节识别正则 ──
CHAPTER_PATTERNS = [
    r'第[零一二三四五六七八九十百千\d]+章',
    r'第[零一二三四五六七八九十百千\d]+回',
    r'第[零一二三四五六七八九十百千\d]+节',
    r'[Cc]hapter\s+\d+',
    r'CHAPTER\s+\d+',
    r'[Cc]hapter\s+[IVX]+\.?',
    r'CHAPTER\s+[IVX]+\.?',
    r'[Ll]etter\s+(\d+|[IVX]+)\.?',
    r'[Pp]art\s+(\d+|[IVX]+)\.?',
    r'[Bb]ook\s+(\d+|[IVX]+)\.?',
    r'[Vv]olume\s+(\d+|[IVX]+)\.?',
]
