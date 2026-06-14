# LAB-2 FastMCP — MCP 開發實作 - 環境準備

以 Docker Compose 啟動一個 PostgreSQL 與一個「使用者管理 Demo」網頁應用(demo-app),
DB 首次啟動會自動建立資料表、種子資料、稽核紀錄與使用者管理函式,demo-app 則提供
登入 / 登出與使用者管理的前後端介面。

本 Lab 以這套已可運作的「網頁應用 + 資料庫」為基礎,接著示範如何用 FastMCP 開發自己的
MCP Server,讓 Copilot 能直接操作這套服務。

## 檔案結構介紹

```
mcp-lab/
├── docker-compose.lab2.yml     
├── demo-db/
│   └── init/                   # 首次啟動自動執行的初始化腳本(依檔名順序)
│       ├── 01_schema.sql       # 資料表:roles / departments / users + v_users 檢視
│       ├── 02_seed.sql         # 種子資料:3 種權限、4 個部門、5 位示範使用者
│       └── 03_procedures.sql   # audit_log 稽核表 + 使用者管理函式
└── demo-app/                   # 使用者管理 Demo(前端 + 後端)
    ├── app.py                  # 後端:FastAPI,以 psycopg 呼叫 demo-db 既有函式 / 檢視
    ├── requirements.txt        # 後端相依套件(fastapi / uvicorn / psycopg)
    ├── Dockerfile              # demo-app 容器映像建置定義
    ├── .dockerignore           # 建置映像時排除的檔案
    ├── README.md               # demo-app 功能與本機啟動說明
    └── static/                 # 前端:純 HTML / CSS / 原生 JavaScript
        ├── index.html
        ├── style.css
        └── app.js
```

**資料表重點**

| 資料表 | 用途 |
|--------|------|
| `roles` | 權限:`admin` / `write` / `read` |
| `departments` | 部門:IT / Sales / HR / Finance |
| `users` | 使用者主檔(密碼以 bcrypt 雜湊儲存,不存明碼) |
| `audit_log` | 操作稽核紀錄(建立/停用/改權限/改密碼/登入) |
| `v_users` | 將代碼 join 成易讀文字的查詢檢視 |

**demo-app**:一個簡單的「前端 + 後端」網頁應用,串接 `demo-db`,示範登入 / 登出與使用者管理。
後端為 Python + FastAPI,所有資料操作都呼叫 `demo-db` 既有的函式與檢視
(`fn_verify_login`、`fn_create_user`、`fn_set_user_active`、`fn_change_user_role`、
`fn_change_password`、`v_users`、`audit_log`);前端為純 HTML / CSS / 原生 JavaScript,
無需打包工具。容器啟動後監聽 `localhost:8080`。

## 啟動方法與說明

### Docker 服務啟動

```bash
# 背景啟動容器(首次啟動會自動執行 demo-db/init 內的初始化腳本,並建置 demo-app 映像)
docker compose -f docker-compose.lab2.yml up -d

# 確認兩個容器狀態(postgres 應為 healthy)
docker compose -f docker-compose.lab2.yml ps

# 查看啟動 / 初始化日誌
docker compose -f docker-compose.lab2.yml logs -f
```

啟動後:

- PostgreSQL 監聽本機 `localhost:5432`
  連線字串:`postgresql://postgres:postgres@localhost:5432/user_management_demo`
- demo-app 監聽本機 `localhost:8080`,開啟瀏覽器:<http://localhost:8080>

demo-app 以 `depends_on` 等待 postgres `healthy` 後才啟動,並透過同一 compose 網路以服務名
`postgres` 連線資料庫。

### 驗證

開啟 <http://localhost:8080>,以示範帳號登入(來自 demo-db 種子資料):

| Email | 密碼 | 權限 |
|-------|------|------|
| alice@demo.local | Admin@123 | admin |
| bob@demo.local | Write@123 | write |
| carol@demo.local | Read@123 | read |

登入後可看到使用者清單;以 alice(admin)登入可新增使用者、變更權限、啟用 / 停用與變更密碼。

### 停止

```bash
# 停止並移除容器(資料保留在 volume,下次啟動沿用)
docker compose -f docker-compose.lab2.yml down

# 僅暫停容器(不移除,可用 docker compose start 復原)
docker compose -f docker-compose.lab2.yml stop
```

### 完全重置(清除資料,重新初始化)

初始化腳本只在資料目錄為空時執行。若修改了 `demo-db/init` 內的腳本並想重跑,
必須先刪除 volume:

```bash
# 停止並一併刪除資料 volume,下次啟動會重新執行 demo-db/init
docker compose -f docker-compose.lab2.yml down -v
docker compose -f docker-compose.lab2.yml up -d
```
