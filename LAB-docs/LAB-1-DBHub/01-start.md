# LAB-1 DataHUB — MCP 與 Database

以 Docker Compose 啟動一個 PostgreSQL，首次啟動會自動建立資料表、種子資料、
稽核紀錄與使用者管理函式，用來示範「登入與使用者權限管理」。

資料庫建立後會包含範例資料，即可透過 Copilot MCP - DBHub

## 檔案結構介紹

```
mcp-lab/
├── docker-compose.lab1.yml          # PostgreSQL 服務定義(映像、連接埠、volume、健康檢查)
├── .env.example                # 連線設定範本(帳號、密碼、資料庫名稱)
├── .env                        # 實際連線設定(由 .env.example 複製,不進版控)
└── demo-db/
    └── init/                   # 首次啟動自動執行的初始化腳本(依檔名順序)
        ├── 01_schema.sql       # 資料表:roles / departments / users + v_users 檢視
        ├── 02_seed.sql         # 種子資料:3 種權限、4 個部門、5 位示範使用者
        └── 03_procedures.sql   # audit_log 稽核表 + 使用者管理函式
```

**初始化機制**:`demo-db/init` 以 bind mount 掛載到容器的
`/docker-entrypoint-initdb.d`，PostgreSQL **僅在資料目錄為空(首次啟動)時**
依檔名順序執行其中的 `*.sql`。資料本身存放在具名 volume `pg-data`(由 Docker 管理)。

**資料表重點**

| 資料表 | 用途 |
|--------|------|
| `roles` | 權限:`admin` / `write` / `read` |
| `departments` | 部門:IT / Sales / HR / Finance |
| `users` | 使用者主檔(密碼以 bcrypt 雜湊儲存,不存明碼) |
| `audit_log` | 操作稽核紀錄(建立/停用/改權限/改密碼/登入) |
| `v_users` | 將代碼 join 成易讀文字的查詢檢視 |

## 啟動方法與說明

###  Docker PostgreSQL 啟動

```bash
# 背景啟動容器(首次啟動會自動執行 demo-db/init 內的初始化腳本)
docker compose -f docker-compose.lab1.yml up -d

# 確認容器狀態為 healthy
docker compose -f docker-compose.lab1.yml ps

# 查看啟動 / 初始化日誌
docker compose -f docker-compose.lab1.yml logs -f postgres
```

啟動後,PostgreSQL 監聽本機 `localhost:5432`。
連線字串:`postgresql://postgres:postgres@localhost:5432/user_management_demo`

### 驗證

```bash
# 查詢所有使用者
docker exec -it postgres psql -U postgres -d user_management_demo \
  -c "SELECT * FROM v_users;"

# 測試登入(回傳 login_ok / permission / department)
docker exec -it postgres psql -U postgres -d user_management_demo \
  -c "SELECT * FROM fn_verify_login('alice@demo.local','Admin@123');"

### 停止

```bash
# 停止並移除容器(資料保留在 volume,下次啟動沿用)
docker compose -f docker-compose.lab1.yml down

# 僅暫停容器(不移除,可用 docker compose start 復原)
docker compose -f docker-compose.lab1.yml stop
```

### 完全重置(清除資料,重新初始化)

初始化腳本只在資料目錄為空時執行。若修改了 `demo-db/init` 內的腳本並想重跑,
必須先刪除 volume:

```bash
# 停止並一併刪除資料 volume,下次啟動會重新執行 demo-db/init
docker compose -f docker-compose.lab1.yml down -v
docker compose -f docker-compose.lab1.yml up -d
```

###  Copilot DBHub

[DBHub](https://github.com/bytebase/dbhub) 是 Bytebase 開發的 MCP Server，
讓 GitHub Copilot 可以直接對資料庫執行 SQL 查詢與結構探索。

#### 安裝（透過 VS Code MCP 擴充）

1. 前往 "Copilot 設定" 頁面
2. 選擇 "MCP Servers"
3. 於 "Marketplace" 搜尋 "DBHub"
4. 點選 "Install"
5. 右鍵啟動 "Start Server"
6. 第一次會需要填入 "DB 資訊"
> 本 Lab：`postgresql://postgres:postgres@localhost:5432/user_management_demo`
> stdio / http => 選擇 stdio
7. 完成後即可透過 Copilot Chat 進行互動

#### 在 Copilot Chat 測試

確認 PostgreSQL 容器已啟動（`docker compose -f docker-compose.lab1.yml up -d`）後，在 Copilot Chat（Agent 模式）輸入：

```
列出 user_management_demo 資料庫中所有資料表
```

```
查詢所有使用者
```

```
測試 alice，回傳權限與部門
```

Copilot 會透過 DBHub MCP 將這些自然語言需求轉成對 PostgreSQL 的查詢操作，實際上仍是以 SQL 與資料庫互動；只是使用者不需要手動輸入 `psql` 或撰寫 SQL。DBHub 會根據連線設定直接連到 `user_management_demo`，執行查詢後再把結果回傳給 Copilot 顯示

