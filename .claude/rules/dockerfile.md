---
paths:
  - "**/Dockerfile"
  - "**/Dockerfile.*"
  - "**/*.dockerfile"
---

# Dockerfile 撰寫建議

編輯或撰寫 Dockerfile 時，依下列原則檢查，並在建議中指出具體違反的行（檔名 + 行號）

## Layer 快取

- 相依套件安裝（`pip install` 等）要放在 `COPY . .`（複製原始碼）之前，讓套件層在
  原始碼變動時仍可命中快取；只有 `requirements.txt`（或等價的相依清單檔）先 `COPY`
- 指令依變動頻率排序：越少變動的放越前面

## 映像大小 / 安全性

- 優先用 `-slim` / alpine 等精簡基底映像，非必要不裝額外系統套件
- `pip install` 加 `--no-cache-dir`，避免留下套件快取
- 不要把密碼、API key 等敏感資訊寫死在 `ENV` / `ARG` 或 `COPY` 進映像；應在執行期以
  環境變數或 secret 注入
- 基底映像釘住明確版本（如 `python:3.13-slim`），避免 `latest`，確保建置可重現

## 明確性

- `EXPOSE` 標示服務實際監聽的 port，且與 `CMD` 啟動的 port 一致
- `CMD` 用 exec form（`["cmd", "arg"]`）而非 shell form，確保訊號能正確傳遞、
  `docker stop` 能正常運作
- bind 位址一律 `0.0.0.0`；連線目標（如資料庫、其他服務）以 compose 服務名稱指定，
  不要寫死 `localhost`（本專案跨容器連線的既有慣例，見 `docker-compose.lab2.yml`）

## 其他

- 確認有對應的 `.dockerignore`，排除 `.git`、`.venv`、`__pycache__`、`.env`、
  測試/文件等建置不需要的檔案
- 若建置階段（如編譯工具鏈）明顯可與執行階段分離，評估用多階段建置
  （multi-stage build）縮小最終映像
