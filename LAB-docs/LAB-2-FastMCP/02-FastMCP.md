# LAB-2 FastMCP — MCP 開發實作 - 開發與測試

承接 `01-start.md`(已啟動 demo-app + demo-db),本章把 demo-app 包成一個 AI 可呼叫的
**MCP Server(demo-mcp)**設計取向是「包服務、不直連 DB」:demo-mcp 只透過 HTTP 呼叫

連線鏈:`AI Client → demo-mcp → demo-app → demo-db`

## MCP 框架簡介

[MCP(Model Context Protocol)](https://modelcontextprotocol.io/) 是讓 AI 客戶端
(Copilot / Claude Desktop 等)呼叫外部能力的標準協議
[FastMCP](https://gofastmcp.com/) 則是用 Python 開發 MCP Server 的高階框架:

- 一個 Python function → 一個 MCP 能力,協議細節(註冊 / 驗證 / transport)由框架代勞
- type hints → 參數，LLM 靠這份 schema 知道「呼叫這個工具時要傳哪些參數、什麼型別」。沒有 type hints，FastMCP 就無法產生正確的 schema
```
def get_user(email: str) -> dict:
    ...
#              ↑ 參數型別   ↑ 回傳型別
```
- docstring → 能力說明，docstring 寫得越精準，LLM 選用工具的準確率就越高
```
@mcp.tool(annotations={"title": "取得單一使用者", "readOnlyHint": True})
def get_user(email: str) -> dict:
    """以 Email 取得單一使用者的資料找不到時回報錯誤"""
    #  ↑ 這段文字會透過 MCP 協定傳給 LLM
```
- 同一份能力可跑不同 transport(stdio / HTTP),改 transport 不動能力

**MCP三元素**(本 Lab 皆有示範):

| 能力 | 角色 | 一句話 | 本 Lab 範例 |
|------|------|--------|-------------|
| **Tool** | 動作(會做事) | Tool 是動作 | `list_users`、`create_user` |
| **Resource** | 資料(唯讀來源) | Resource 是資料 | `audit://recent`、`user://{email}` |
| **Prompt** | 任務起手式(可重用模板) | Prompt 是任務起手式 | `review_user_access` |

**Transport 與本 Lab 選擇**:stdio 適合本機開發(Host 啟動 subprocess);HTTP 則讓
Server 跑在遠端 / 容器、可團隊共享本 Lab **採用 HTTP**,並在本機以 Docker 模擬「遠端」,
demo-mcp 對外端點為 `http://localhost:8000/mcp`

## 檔案路徑介紹

```
mcp-lab/
├── server.py                   # demo-mcp 主程式(FastMCP,HTTP transport)
├── requirements.txt            # demo-mcp 相依套件(fastmcp / httpx)
├── Dockerfile                  # demo-mcp 容器映像建置定義
├── .dockerignore               # 建置 demo-mcp 映像時排除的檔案
├── test_server.py              # 本地檢查腳本(FastMCP in-memory Client)
├── .env.example                # 連線 / 帳密設定範本(複製成 .env,不進版控)
├── .vscode/
│   └── mcp.json                # Copilot 整合設定(HTTP:type + url,根鍵 servers)
├── docker-compose.lab2.yml     # postgres + demo-app + demo-mcp 三個服務定義
├── demo-app/                   # 被包裝的使用者管理 Demo(前端 + 後端,見 01-start.md)
└── demo-db/                    # PostgreSQL 初始化腳本(見 01-start.md)
```

**`server.py` 能力一覽**

| 類型 | 名稱 | 對應 demo-app 端點 | 標註 |
|------|------|--------------------|------|
| Tool(唯讀) | `list_users` | `GET /api/users` | readOnly |
| Tool(唯讀) | `get_user` | `GET /api/users`(過濾) | readOnly |
| Tool(唯讀) | `verify_login` | `POST /api/login`(獨立連線) | readOnly |
| Tool(唯讀) | `list_metadata` | `GET /api/meta` | readOnly |
| Tool(唯讀) | `recent_audit` | `GET /api/audit` | readOnly |
| Tool(寫入) | `create_user` | `POST /api/users` | — |
| Tool(寫入) | `set_user_active` | `POST /api/users/{email}/active` | destructive |
| Tool(寫入) | `change_user_role` | `POST /api/users/{email}/role` | destructive |
| Tool(寫入) | `change_password` | `POST /api/users/{email}/password` | destructive |
| Resource | `audit://recent` | `GET /api/audit` | 唯讀資料 |
| Resource Template | `user://{email}` | `GET /api/users`(過濾) | 唯讀資料 |
| Prompt | `review_user_access` | — | 任務模板 |

**環境變數**(於 `docker-compose.lab2.yml` 設定):

| 變數 | 用途 | 預設 |
|------|------|------|
| `DEMO_APP_URL` | demo-app base URL(compose 內用服務名) | `http://localhost:8080` |
| `DEMO_APP_EMAIL` | demo-mcp 操作 demo-app 的帳號(寫入需 admin) | `alice@demo.local` |
| `DEMO_APP_PASSWORD` | 上述帳號密碼 | `Admin@123` |
| `MCP_HOST` / `MCP_PORT` | HTTP transport bind 位址 | `0.0.0.0` / `8000` |

**連線分層**:

- 對外:host / VS Code → demo-mcp = `localhost:8000`
- 內層:demo-mcp → demo-app = 服務名 `demo-app:8080`(非 localhost)
- 底層:demo-app → DB = 服務名 `postgres:5432`
- bind 一律 `0.0.0.0`,連線目標的主機名用服務名而非 localhost

## 啟動與停止

### 以 Docker 啟動(連同 demo-app / postgres)

`docker-compose.lab2.yml` 已包含 `demo-mcp` 服務,可以啟動整套 Lab 服務:

```bash
# 背景啟動三個容器(postgres → demo-app → demo-mcp)
docker compose -f docker-compose.lab2.yml up -d --build

# 確認狀態(postgres 應為 healthy)
docker compose -f docker-compose.lab2.yml ps

# 查看 demo-mcp 日誌
docker compose -f docker-compose.lab2.yml logs -f demo-mcp
```

啟動後,demo-mcp 對外端點為 <http://localhost:8000/mcp>

### 停止

```bash
# 停止並移除容器(資料保留在 volume)
docker compose -f docker-compose.lab2.yml down

# 僅停 demo-mcp 一個服務
docker compose -f docker-compose.lab2.yml stop demo-mcp
```

## 測試方法

核心是 FastMCP 的 **in-memory Client**:把 server 物件直接交給 `Client(server.mcp)`

`test_server.py` 就是一支用到此功能的**純腳本**,直接執行即可,分兩段:

- **能力盤點**:列出 tools / resources / prompts 與唯讀標註

```bash
DEMO_APP_URL=http://localhost:8080 python test_server.py
```

> in-memory Client 是 FastMCP 的能力(核心)
> 本 Lab 採用最直接的腳本寫法

**互動檢查(Inspector)**:

```bash
# 以 FastMCP 開發模式開啟 Inspector,手動列出 / 呼叫能力
fastmcp dev inspector server.py
```

**直接以 Client 連 HTTP 端點驗證**(確認整條鏈路 demo-mcp → demo-app → postgres):

## 與 Copilot 整合

- **Copilot**:`.vscode/mcp.json`,HTTP 用 `type` + `url`,根鍵為 `servers`
  (本 Lab 已附,指向 `http://localhost:8000/mcp`)於 Agent 模式測:
  列出使用者、驗證登入、讀稽核紀錄
