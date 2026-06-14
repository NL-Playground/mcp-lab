"""
demo-app — 使用者管理 Demo 後端 (FastAPI)

串接 demo-db (PostgreSQL)，所有資料操作都呼叫資料庫中既有的函式 / 檢視:
  - fn_verify_login        登入驗證
  - v_users                使用者清單 (代碼已 join 成易讀文字)
  - fn_create_user         新增使用者
  - fn_set_user_active     啟用 / 停用
  - fn_change_user_role    變更權限
  - fn_change_password     變更密碼
  - audit_log              稽核紀錄

執行:
    cd demo-app
    uvicorn app:app --reload --port 8080
然後開啟 http://localhost:8080
"""
from __future__ import annotations

import os
import secrets
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

import psycopg
from psycopg.rows import dict_row
from fastapi import Cookie, Depends, FastAPI, HTTPException, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# 設定
# ---------------------------------------------------------------------------
DB_DSN = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/user_management_demo",
)
STATIC_DIR = Path(__file__).parent / "static"
SESSION_COOKIE = "session"

app = FastAPI(title="demo-app — User Management")

# 簡易的記憶體 session 儲存 (demo 用途;正式環境請改用 Redis / DB)
# token -> {"email", "user_name", "permission", "department"}
SESSIONS: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# 資料庫
# ---------------------------------------------------------------------------
@contextmanager
def get_db():
    """每個請求開一條連線;以 dict_row 取得欄位名稱對應的 dict。"""
    conn = psycopg.connect(DB_DSN, row_factory=dict_row, autocommit=True)
    try:
        yield conn
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Session / 權限相依
# ---------------------------------------------------------------------------
def current_user(session: Optional[str] = Cookie(default=None)) -> dict:
    user = SESSIONS.get(session) if session else None
    if not user:
        raise HTTPException(status_code=401, detail="尚未登入")
    return user


def require_admin(user: dict = Depends(current_user)) -> dict:
    if user["permission"] != "admin":
        raise HTTPException(status_code=403, detail="需要 admin 權限才能執行此操作")
    return user


# ---------------------------------------------------------------------------
# 請求 / 回應模型
# ---------------------------------------------------------------------------
class LoginIn(BaseModel):
    email: str
    password: str


class CreateUserIn(BaseModel):
    user_name: str
    email: str
    password: str
    role: str          # admin / write / read
    department: str     # IT / Sales / HR / Finance


class ActiveIn(BaseModel):
    is_active: bool


class RoleIn(BaseModel):
    role: str


class PasswordIn(BaseModel):
    password: str


# ---------------------------------------------------------------------------
# Auth API
# ---------------------------------------------------------------------------
@app.post("/api/login")
def login(body: LoginIn, response: Response):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM fn_verify_login(%s, %s)", (body.email, body.password)
        ).fetchone()

    if not row or not row["login_ok"]:
        raise HTTPException(status_code=401, detail="帳號或密碼錯誤,或帳號已停用")

    token = secrets.token_urlsafe(32)
    SESSIONS[token] = {
        "email": body.email,
        "permission": row["permission"],
        "department": row["department"],
    }
    # 補上 user_name 方便前端顯示
    with get_db() as conn:
        u = conn.execute(
            "SELECT user_name FROM v_users WHERE email = %s", (body.email,)
        ).fetchone()
    SESSIONS[token]["user_name"] = u["user_name"] if u else body.email

    response.set_cookie(
        SESSION_COOKIE, token, httponly=True, samesite="lax", max_age=60 * 60 * 8
    )
    return SESSIONS[token]


@app.post("/api/logout")
def logout(response: Response, session: Optional[str] = Cookie(default=None)):
    if session:
        SESSIONS.pop(session, None)
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}


@app.get("/api/me")
def me(user: dict = Depends(current_user)):
    return user


# ---------------------------------------------------------------------------
# 中繼資料 (下拉選單用)
# ---------------------------------------------------------------------------
@app.get("/api/meta")
def meta(_: dict = Depends(current_user)):
    with get_db() as conn:
        roles = conn.execute(
            "SELECT code, description FROM roles ORDER BY role_id"
        ).fetchall()
        depts = conn.execute(
            "SELECT name FROM departments ORDER BY name"
        ).fetchall()
    return {"roles": roles, "departments": [d["name"] for d in depts]}


# ---------------------------------------------------------------------------
# 使用者管理 API
# ---------------------------------------------------------------------------
@app.get("/api/users")
def list_users(_: dict = Depends(current_user)):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM v_users ORDER BY user_id"
        ).fetchall()
    return rows


@app.post("/api/users")
def create_user(body: CreateUserIn, admin: dict = Depends(require_admin)):
    try:
        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM fn_create_user(%s, %s, %s, %s, %s, %s)",
                (
                    body.user_name,
                    body.email,
                    body.password,
                    body.role,
                    body.department,
                    admin["email"],
                ),
            ).fetchone()
        return row
    except psycopg.errors.RaiseException as e:
        raise HTTPException(status_code=400, detail=_pg_msg(e))


@app.post("/api/users/{email}/active")
def set_active(email: str, body: ActiveIn, admin: dict = Depends(require_admin)):
    try:
        with get_db() as conn:
            conn.execute(
                "SELECT fn_set_user_active(%s, %s, %s)",
                (email, body.is_active, admin["email"]),
            )
        return {"ok": True}
    except psycopg.errors.RaiseException as e:
        raise HTTPException(status_code=400, detail=_pg_msg(e))


@app.post("/api/users/{email}/role")
def change_role(email: str, body: RoleIn, admin: dict = Depends(require_admin)):
    try:
        with get_db() as conn:
            conn.execute(
                "SELECT fn_change_user_role(%s, %s, %s)",
                (email, body.role, admin["email"]),
            )
        return {"ok": True}
    except psycopg.errors.RaiseException as e:
        raise HTTPException(status_code=400, detail=_pg_msg(e))


@app.post("/api/users/{email}/password")
def change_password(email: str, body: PasswordIn, user: dict = Depends(current_user)):
    # admin 可改任何人;一般使用者只能改自己的密碼
    if user["permission"] != "admin" and user["email"] != email:
        raise HTTPException(status_code=403, detail="只能變更自己的密碼")
    try:
        with get_db() as conn:
            conn.execute(
                "SELECT fn_change_password(%s, %s, %s)",
                (email, body.password, user["email"]),
            )
        return {"ok": True}
    except psycopg.errors.RaiseException as e:
        raise HTTPException(status_code=400, detail=_pg_msg(e))


@app.get("/api/audit")
def audit(_: dict = Depends(require_admin), limit: int = 50):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT action, target_email, performed_by, detail, created_at "
            "FROM audit_log ORDER BY audit_id DESC LIMIT %s",
            (limit,),
        ).fetchall()
    return rows


# ---------------------------------------------------------------------------
# 工具 / 靜態頁面
# ---------------------------------------------------------------------------
def _pg_msg(e: psycopg.Error) -> str:
    """把 PostgreSQL RAISE EXCEPTION 的訊息取出給前端。"""
    msg = (getattr(e, "diag", None) and e.diag.message_primary) or str(e)
    return msg.strip()


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/", StaticFiles(directory=STATIC_DIR), name="static")
