"""认证模块 —— Token + 用户注册/登录/密码重置"""

import hashlib
import hmac
import time
import base64
import secrets
import logging
import smtplib
from email.mime.text import MIMEText
from typing import Optional
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from app.config import SECRET_KEY, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM
from app.database import get_db

logger = logging.getLogger(__name__)

TOKEN_TTL = 7 * 24 * 3600  # 7 天


# ── Token ──

def generate_token(user_id: int) -> str:
    """生成登录 token"""
    ts = str(int(time.time()))
    payload = f"{ts}:{user_id}"
    sig = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    token = base64.urlsafe_b64encode(f"{ts}:{user_id}:{sig}".encode()).decode()
    return token


def verify_token(token: str) -> Optional[int]:
    """验证 token，成功返回 user_id，失败返回 None"""
    try:
        raw = base64.urlsafe_b64decode(token.encode()).decode()
        parts = raw.split(":", 2)
        if len(parts) != 3:
            return None
        ts_str, user_id_str, sig = parts
        ts = int(ts_str)
        if time.time() - ts > TOKEN_TTL:
            return None
        expected_payload = f"{ts_str}:{user_id_str}"
        expected_sig = hmac.new(SECRET_KEY.encode(), expected_payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None
        return int(user_id_str)
    except Exception:
        return None


# ── 密码处理 ──

def hash_password(password: str) -> str:
    """SHA-256 + salt"""
    salt = secrets.token_hex(16)
    h = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}:{h}"


def check_password(password: str, stored: str) -> bool:
    """验证密码"""
    try:
        salt, h = stored.split(":", 1)
        expected = hashlib.sha256((salt + password).encode()).hexdigest()
        return hmac.compare_digest(expected, h)
    except Exception:
        return False


# ── 用户操作 ──

def find_user(email: str = None, phone: str = None) -> Optional[dict]:
    """按邮箱或手机号查找用户"""
    db = get_db()
    try:
        if email:
            row = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        elif phone:
            row = db.execute("SELECT * FROM users WHERE phone = ?", (phone,)).fetchone()
        else:
            return None
        return dict(row) if row else None
    finally:
        db.close()


def create_user(email: str, phone: str, password: str) -> int:
    """注册新用户，返回 user_id"""
    db = get_db()
    try:
        cur = db.execute(
            "INSERT INTO users (email, phone, password_hash) VALUES (?, ?, ?)",
            (email, phone, hash_password(password)),
        )
        db.commit()
        return cur.lastrowid
    except Exception as e:
        db.rollback()
        if "UNIQUE" in str(e).upper():
            raise ValueError("该邮箱或手机号已注册")
        raise
    finally:
        db.close()


def reset_user_password(email: str = None, phone: str = None, new_password: str = None) -> bool:
    """重置密码（本地工具：直接重置为指定密码或随机生成）"""
    db = get_db()
    try:
        if email:
            row = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        elif phone:
            row = db.execute("SELECT id FROM users WHERE phone = ?", (phone,)).fetchone()
        else:
            return False
        if not row:
            return False
        new_pw = new_password or secrets.token_hex(6)
        new_hash = hash_password(new_pw)
        db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, row["id"]))
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"[Auth] 重置密码失败: {e}")
        return False
    finally:
        db.close()


def get_user_count() -> int:
    """用户总数（用于判断是否需要初始化管理员）"""
    db = get_db()
    try:
        row = db.execute("SELECT COUNT(*) as cnt FROM users").fetchone()
        return row["cnt"]
    finally:
        db.close()


# ── 验证码（内存存储，5 分钟有效）──

_code_store: dict = {}  # key → {"code": ..., "expires_at": ...}


def _smtp_enabled() -> bool:
    """SMTP 是否已配置"""
    return bool(SMTP_USER and SMTP_PASSWORD)


def _send_email(to: str, subject: str, body: str) -> bool:
    """通过 QQ 邮箱 SMTP 发送邮件"""
    if not _smtp_enabled():
        logger.warning("[Auth] SMTP 未配置，邮件发送跳过")
        return False
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = SMTP_FROM
        msg["To"] = to
        if SMTP_PORT == 465:
            server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=10)
        else:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10)
            server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_FROM, [to], msg.as_string())
        server.quit()
        logger.info(f"[Auth] 邮件已发送: {to}")
        return True
    except Exception as e:
        logger.error(f"[Auth] 邮件发送失败: {e}")
        return False


def generate_verification_code(key: str) -> str:
    """生成 6 位验证码；如果是邮箱则发送邮件"""
    code = str(secrets.randbelow(900000) + 100000)
    _code_store[key] = {"code": code, "expires_at": time.time() + 300}

    # 尝试发送邮件（仅当 key 是邮箱且 SMTP 已配置）
    if "@" in key and _smtp_enabled():
        _send_email(
            to=key,
            subject="InkReel 验证码",
            body=f"您的验证码是：{code}\n\n5 分钟内有效。\n\n— InkReel",
        )
    # 手机号：目前没有短信服务，会在 API 响应中返回（仅本地开发模式）

    return code


def send_code_response(key: str, code: str) -> dict:
    """构建发送验证码的响应，告知是否已实际发送"""
    if "@" in key:
        if _smtp_enabled():
            return {"status": "ok", "message": f"验证码已发送至 {key}，请查收邮件"}
        else:
            # SMTP 未配置时本地显示（开发模式）
            return {"status": "ok", "code": code, "message": f"SMTP 未配置，验证码：{code}"}
    else:
        # 手机号
        return {"status": "ok", "code": code, "message": f"短信未配置，验证码：{code}"}


def check_verification_code(key: str, code: str) -> bool:
    """校验验证码，成功即删除（一次性使用）"""
    entry = _code_store.get(key)
    if not entry:
        return False
    if time.time() > entry["expires_at"]:
        del _code_store[key]
        return False
    if entry["code"] != str(code).strip():
        return False
    del _code_store[key]
    return True


# ── 中间件 ──

class AuthMiddleware(BaseHTTPMiddleware):
    """API 认证中间件"""

    SKIP_PATHS = {
        "/api/auth/login",
        "/api/auth/register",
        "/api/auth/send-code",
        "/api/auth/reset-password",
        "/api/auth/check",
        "/api/health",
        "/api/mode",
    }

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if path in self.SKIP_PATHS or not path.startswith("/api/"):
            return await call_next(request)

        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="未登录")

        user_id = verify_token(auth[7:])
        if user_id is None:
            raise HTTPException(status_code=401, detail="token 无效或已过期")

        # 将 user_id 注入 request state 供业务使用
        request.state.user_id = user_id
        return await call_next(request)
