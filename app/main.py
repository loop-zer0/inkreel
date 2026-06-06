"""FastAPI 应用主入口 — InkReel"""

import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response, JSONResponse
import os

from app.config import FRONTEND_DIR
from app.auth import (
    AuthMiddleware, generate_token, verify_token,
    find_user, create_user, check_password, reset_user_password, get_user_count,
    generate_verification_code, check_verification_code, send_code_response,
)
from app.routers import novels, convert, scripts, system

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="InkReel — AI 小说转剧本工具")


@app.on_event("startup")
async def seed_default_user():
    """首次启动自动创建默认账户：admin@inkreel.local / inkreel"""
    from app.database import get_db
    db = get_db()
    try:
        count = db.execute("SELECT COUNT(*) as cnt FROM users").fetchone()["cnt"]
        if count == 0:
            from app.auth import hash_password
            pw_hash = hash_password("inkreel")
            db.execute(
                "INSERT INTO users (email, phone, password_hash) VALUES (?, ?, ?)",
                ("admin@inkreel.local", "", pw_hash),
            )
            db.commit()
            logger.info("[Auth] 已创建默认账户: admin@inkreel.local / inkreel")
    finally:
        db.close()

# CORS（必须放在 Auth 中间件之前）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

# Auth 中间件
app.add_middleware(AuthMiddleware)

# 注册业务路由
app.include_router(novels.router)
app.include_router(convert.router)
app.include_router(scripts.router)
app.include_router(system.router)


# ── Auth 路由 ──

@app.post("/api/auth/send-code")
async def auth_send_code(req: dict):
    """发送验证码：邮箱走 SMTP，手机号本地显示"""
    email = (req.get("email") or "").strip()
    phone = (req.get("phone") or "").strip()

    if not email and not phone:
        return JSONResponse({"status": "error", "message": "请输入邮箱或手机号"}, status_code=400)

    key = email or phone
    code = generate_verification_code(key)
    return send_code_response(key, code)


@app.post("/api/auth/register")
async def auth_register(req: dict):
    """注册新用户（需验证码）"""
    email = (req.get("email") or "").strip()
    phone = (req.get("phone") or "").strip()
    password = (req.get("password") or "").strip()
    code = (req.get("code") or "").strip()

    if not email and not phone:
        return JSONResponse({"status": "error", "message": "请输入邮箱或手机号"}, status_code=400)
    if len(password) < 4:
        return JSONResponse({"status": "error", "message": "密码至少 4 位"}, status_code=400)

    # 验证码校验
    key = email or phone
    if not check_verification_code(key, code):
        return JSONResponse({"status": "error", "message": "验证码错误或已过期"}, status_code=400)

    # 检查是否已存在
    if email and find_user(email=email):
        return JSONResponse({"status": "error", "message": "该邮箱已注册"}, status_code=400)
    if phone and find_user(phone=phone):
        return JSONResponse({"status": "error", "message": "该手机号已注册"}, status_code=400)

    try:
        user_id = create_user(email=email, phone=phone, password=password)
        token = generate_token(user_id)
        logger.info(f"[Auth] 新用户注册: id={user_id}")
        return {"status": "ok", "token": token, "message": "注册成功"}
    except ValueError as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=400)


@app.post("/api/auth/login")
async def auth_login(req: dict):
    """邮箱/手机号 + 密码登录"""
    account = (req.get("account") or "").strip()
    password = (req.get("password") or "").strip()

    if not account or not password:
        return JSONResponse({"status": "error", "message": "请输入账号和密码"}, status_code=400)

    # 判断是邮箱还是手机号
    user = None
    if "@" in account:
        user = find_user(email=account)
    else:
        user = find_user(phone=account)

    if not user:
        return JSONResponse({"status": "error", "message": "账号不存在，请先注册"}, status_code=401)

    if not check_password(password, user["password_hash"]):
        return JSONResponse({"status": "error", "message": "密码错误"}, status_code=401)

    token = generate_token(user["id"])
    return {"status": "ok", "token": token, "message": "登录成功"}


@app.post("/api/auth/reset-password")
async def auth_reset_password(req: dict):
    """找回密码：验证码通过后重置"""
    email = (req.get("email") or "").strip()
    phone = (req.get("phone") or "").strip()
    code = (req.get("code") or "").strip()

    if not email and not phone:
        return JSONResponse({"status": "error", "message": "请输入邮箱或手机号"}, status_code=400)

    user = None
    if email:
        user = find_user(email=email)
    elif phone:
        user = find_user(phone=phone)

    if not user:
        return JSONResponse({"status": "error", "message": "该账号未注册"}, status_code=404)

    # 验证码校验
    key = email or phone
    if not check_verification_code(key, code):
        return JSONResponse({"status": "error", "message": "验证码错误或已过期"}, status_code=400)

    # 生成新密码并重置
    import secrets
    new_password = secrets.token_hex(6)
    ok = reset_user_password(email=email, phone=phone, new_password=new_password)
    if ok:
        logger.info(f"[Auth] 密码已重置: user_id={user['id']}")
        return {"status": "ok", "message": "密码已重置", "new_password": new_password}
    return JSONResponse({"status": "error", "message": "重置失败，请重试"}, status_code=500)


@app.get("/api/auth/check")
async def auth_check(request: Request):
    """验证 token 是否有效"""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return JSONResponse({"status": "error", "message": "未登录"}, status_code=401)
    user_id = verify_token(auth[7:])
    if user_id is not None:
        return {"status": "ok"}
    return JSONResponse({"status": "error", "message": "token 无效或已过期"}, status_code=401)


# ── 页面路由 ──

@app.get("/favicon.ico")
async def favicon():
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
           '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
           '<stop offset="0%" stop-color="#5b7a6e"/>'
           '<stop offset="100%" stop-color="#3d5a4e"/>'
           '</linearGradient></defs>'
           '<rect width="32" height="32" rx="6" fill="#1a1a18"/>'
           '<path d="M10 8h2v2h-2zM12 8h2v2h-2zM8 10h2v2h-2zM10 10h2v10h-2zM12 10h2v12h-2zM14 10h2v10h-2zM16 10h2v2h-2zM8 20h2v2h-2zM14 20h2v2h-2zM16 20h2v2h-2z" fill="url(#g)"/>'
           '<circle cx="22" cy="22" r="6" fill="url(#g)" opacity="0.9"/>'
           '<circle cx="22" cy="22" r="3" fill="#1a1a18"/>'
           '</svg>')
    return Response(content=svg, media_type="image/svg+xml")


@app.get("/app")
async def app_page():
    """工具页面（原 index.html）"""
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


@app.get("/")
async def landing():
    """产品介绍页"""
    return FileResponse(os.path.join(FRONTEND_DIR, "landing.html"))
