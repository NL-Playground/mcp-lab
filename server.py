from __future__ import annotations

import os
from typing import Any

import httpx
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

# ---------------------------------------------------------------------------
# 設定
# ---------------------------------------------------------------------------
DEMO_APP_URL = os.getenv("DEMO_APP_URL", "http://localhost:8080").rstrip("/")
DEMO_APP_EMAIL = os.getenv("DEMO_APP_EMAIL", "alice@demo.local")
DEMO_APP_PASSWORD = os.getenv("DEMO_APP_PASSWORD", "Admin@123")

MCP_HOST = os.getenv("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.getenv("MCP_PORT", "8000"))

mcp = FastMCP("demo-mcp")


# ---------------------------------------------------------------------------
# demo-app HTTP 用戶端
#   - 以 cookie session 維持登入狀態 (httpx.Client 會自動保存 cookie)
#   - 第一次呼叫時才登入 (lazy),遇 401 會自動重登一次
# ---------------------------------------------------------------------------
class DemoAppClient:
    """封裝對 demo-app 的 HTTP 呼叫,集中處理登入與錯誤轉譯"""

    def __init__(self, base_url: str, email: str, password: str) -> None:
        self._client = httpx.Client(base_url=base_url, timeout=10.0)
        self._email = email
        self._password = password
        self._logged_in = False

    def _login(self) -> None:
        resp = self._client.post(
            "/api/login", json={"email": self._email, "password": self._password}
        )
        if resp.status_code != 200:
            raise ToolError(
                f"demo-mcp 無法以 {self._email} 登入 demo-app: {_detail(resp)}"
            )
        self._logged_in = True

    def request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        """送出請求;必要時自動登入,並在 session 失效 (401) 時重登一次"""
        if not self._logged_in:
            self._login()

        resp = self._client.request(method, path, **kwargs)
        if resp.status_code == 401:
            # session 可能過期,重登後再試一次
            self._login()
            resp = self._client.request(method, path, **kwargs)

        if resp.status_code >= 400:
            raise ToolError(f"demo-app 回應 {resp.status_code}: {_detail(resp)}")
        return resp

    def get(self, path: str, **kwargs: Any) -> Any:
        return self.request("GET", path, **kwargs).json()

    def post(self, path: str, **kwargs: Any) -> Any:
        return self.request("POST", path, **kwargs).json()


def _detail(resp: httpx.Response) -> str:
    """取出 demo-app 的錯誤訊息 (FastAPI 會放在 JSON 的 detail 欄位)"""
    try:
        body = resp.json()
        if isinstance(body, dict) and "detail" in body:
            return str(body["detail"])
    except Exception:
        pass
    return resp.text.strip() or "(無內容)"


# 模組層級單例,所有 tool / resource 共用同一條登入 session
_app = DemoAppClient(DEMO_APP_URL, DEMO_APP_EMAIL, DEMO_APP_PASSWORD)


# ===========================================================================
# Tools — 唯讀查詢 (query): 不改變狀態,標 readOnlyHint
# ===========================================================================
@mcp.tool(annotations={"title": "列出使用者", "readOnlyHint": True})
def list_users() -> list[dict]:
    """列出所有使用者(姓名 / Email / 權限 / 部門 / 狀態 / 最後登入)

    對應 demo-app 的 GET /api/users(讀 v_users 檢視)
    """
    return _app.get("/api/users")


@mcp.tool(annotations={"title": "取得單一使用者", "readOnlyHint": True})
def get_user(email: str) -> dict:
    """以 Email 取得單一使用者的資料找不到時回報錯誤"""
    users = _app.get("/api/users")
    for u in users:
        if u.get("email") == email:
            return u
    raise ToolError(f"查無使用者: {email}")


@mcp.tool(annotations={"title": "驗證登入", "readOnlyHint": True})
def verify_login(email: str, password: str) -> dict:
    """驗證一組帳號密碼是否正確(由 demo-app / DB 以 bcrypt 驗證)

    回傳 {"login_ok": bool, "permission": ..., "department": ...}
    此操作不影響本 Server 的管理 session(使用獨立連線)
    """
    # 用一條臨時連線,避免覆蓋本 Server 的管理 session
    with httpx.Client(base_url=DEMO_APP_URL, timeout=10.0) as c:
        resp = c.post("/api/login", json={"email": email, "password": password})
    if resp.status_code == 200:
        data = resp.json()
        return {
            "login_ok": True,
            "permission": data.get("permission"),
            "department": data.get("department"),
        }
    if resp.status_code == 401:
        return {"login_ok": False, "permission": None, "department": None}
    raise ToolError(f"驗證時 demo-app 回應 {resp.status_code}: {_detail(resp)}")


@mcp.tool(annotations={"title": "可用的權限與部門", "readOnlyHint": True})
def list_metadata() -> dict:
    """列出可用的權限(roles)與部門(departments),供建立 / 變更使用者時參考

    對應 demo-app 的 GET /api/meta
    """
    return _app.get("/api/meta")


@mcp.tool(annotations={"title": "近期稽核紀錄", "readOnlyHint": True})
def recent_audit(limit: int = 20) -> list[dict]:
    """讀取近期稽核紀錄(建立 / 停用 / 改權限 / 改密碼 / 登入)需要 admin 權限

    對應 demo-app 的 GET /api/audit
    """
    return _app.get("/api/audit", params={"limit": limit})


# ===========================================================================
# Tools — 寫入操作 (side-effect): 會改變狀態,標 readOnlyHint=False
#   destructiveHint: 停用 / 改權限 / 改密碼屬破壞性變更
# ===========================================================================
@mcp.tool(
    annotations={
        "title": "新增使用者",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    }
)
def create_user(
    user_name: str, email: str, password: str, role: str, department: str
) -> dict:
    """新增一位使用者需要 admin 權限

    參數:
      user_name  顯示姓名
      email      登入 Email(需唯一)
      password   初始密碼(由 DB 以 bcrypt 雜湊儲存)
      role       權限: admin / write / read
      department 部門: IT / Sales / HR / Finance
    可先用 list_metadata 確認可用的 role 與 department
    """
    return _app.post(
        "/api/users",
        json={
            "user_name": user_name,
            "email": email,
            "password": password,
            "role": role,
            "department": department,
        },
    )


@mcp.tool(
    annotations={
        "title": "啟用 / 停用使用者",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
    }
)
def set_user_active(email: str, is_active: bool) -> dict:
    """啟用或停用指定使用者需要 admin 權限

    is_active=False 會使該帳號無法登入
    """
    return _app.post(f"/api/users/{email}/active", json={"is_active": is_active})


@mcp.tool(
    annotations={
        "title": "變更使用者權限",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
    }
)
def change_user_role(email: str, role: str) -> dict:
    """變更指定使用者的權限(admin / write / read)需要 admin 權限"""
    return _app.post(f"/api/users/{email}/role", json={"role": role})


@mcp.tool(
    annotations={
        "title": "變更使用者密碼",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
    }
)
def change_password(email: str, password: str) -> dict:
    """變更指定使用者的密碼本 Server 以 admin 身分操作,可變更任何人的密碼"""
    return _app.post(f"/api/users/{email}/password", json={"password": password})


# ===========================================================================
# Resources — 唯讀資料來源,以 URI 取用
# ===========================================================================
@mcp.resource("audit://recent")
def audit_recent() -> list[dict]:
    """近期稽核紀錄(唯讀資料來源,預設 50 筆)"""
    return _app.get("/api/audit", params={"limit": 50})


@mcp.resource("user://{email}")
def user_resource(email: str) -> dict:
    """單一使用者資料(Resource Template,帶 email 參數)"""
    users = _app.get("/api/users")
    for u in users:
        if u.get("email") == email:
            return u
    raise ToolError(f"查無使用者: {email}")


# ===========================================================================
# Prompt — 可重用任務模板
# ===========================================================================
@mcp.prompt
def permission_distribution_review() -> str:
    """整理使用者部門人數比例，並確認 Admin 權限未出現在非技術團隊"""
    return (
        "請執行「權限分配檢索」任務，步驟如下：\n\n"
        "1. 呼叫 list_users 取得所有使用者清單\n"
        "2. 統計各部門的人數，計算每個部門佔總人數的比例，以表格呈現：\n"
        "   | 部門 | 人數 | 比例 |\n"
        "   |------|------|------|\n"
        "3. 統計各權限（admin / write / read）的人數與比例\n"
        "4. 安全性檢查：找出所有 role = admin 的使用者，\n"
        "   確認其部門是否為技術團隊（IT）。\n"
        "   若有 admin 出現在非 IT 部門（如 Sales / HR / Finance），\n"
        "   請列出該使用者並標示為「⚠️ 異常：非技術團隊持有 Admin 權限」\n"
        "5. 最後給出一段摘要說明整體權限分配是否合理，\n"
        "   如有異常請建議是否需要調降權限（執行變更前請先向我確認）"
    )


@mcp.prompt
def review_user_access(email: str) -> str:
    """產生一段「檢視某使用者存取權限」的任務方針"""
    return (
        f"請檢視使用者 {email} 的存取權限是否恰當\n"
        "步驟:\n"
        f"1. 用 get_user 取得 {email} 的權限與部門、是否啟用\n"
        "2. 用 recent_audit 查看與此使用者相關的近期操作紀錄\n"
        "3. 依最小權限原則判斷其權限是否過高,若有疑慮請說明並提出調整建議\n"
        "注意:任何停用或降權的變更都屬破壞性操作,執行前請先向我確認"
    )


if __name__ == "__main__":
    # HTTP transport: 在本機以 Docker 模擬「遠端 / 容器化」的 MCP Server
    # 端點為 http://<host>:<port>/mcp
    mcp.run(transport="http", host=MCP_HOST, port=MCP_PORT)
