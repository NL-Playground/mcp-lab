# demo-app — 使用者管理 Demo

一個簡單的「前端 + 後端」網頁應用,串接 `demo-db` (PostgreSQL),示範
**登入 / 登出** 與 **使用者管理**。

- **後端**:Python + [FastAPI](https://fastapi.tiangolo.com/),以 `psycopg` 連線資料庫,
  所有資料操作都呼叫 `demo-db` 既有的函式與檢視 (`fn_verify_login`、`fn_create_user`、
  `fn_set_user_active`、`fn_change_user_role`、`fn_change_password`、`v_users`、`audit_log`)。
- **前端**:純 HTML / CSS / 原生 JavaScript (`static/`),無需打包工具。

## 功能

| 功能 | 說明 | 權限 |
|------|------|------|
| 登入 / 登出 | 以 email + 密碼登入 (bcrypt 由 DB 驗證),cookie session | 全部 |
| 使用者清單 | 顯示姓名 / Email / 權限 / 部門 / 狀態 / 最後登入 | 登入後 |
| 新增使用者 | 指定姓名、Email、密碼、權限、部門 | admin |
| 變更權限 | admin / write / read | admin |
| 啟用 / 停用 | 切換帳號狀態 | admin |
| 變更密碼 | admin 可改任何人;一般使用者只能改自己 | admin / 本人 |

## 啟動步驟

```bash
# 1. 啟動資料庫 (在專案根目錄)
docker compose up -d

# 2. 安裝相依套件
pip install -r demo-app/requirements.txt

# 3. 啟動應用
cd demo-app
uvicorn app:app --reload --port 8080
```

開啟瀏覽器:<http://localhost:8080>

### 示範帳號 (來自 demo-db 種子資料)

| Email | 密碼 | 權限 |
|-------|------|------|
| alice@demo.local | Admin@123 | admin |
| bob@demo.local | Write@123 | write |
| carol@demo.local | Read@123 | read |

## 設定

連線字串以環境變數 `DATABASE_URL` 覆寫,預設:

```
postgresql://postgres:postgres@localhost:5432/user_management_demo
```

## 備註

- Session 存於後端記憶體 (demo 用途);正式環境請改用 Redis / DB。
- 所有寫入操作都會記錄在 `audit_log`,admin 可透過 `GET /api/audit` 查詢。
