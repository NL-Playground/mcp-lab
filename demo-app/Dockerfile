# demo-app — 使用者管理 Demo (FastAPI)
FROM python:3.13-slim

# 不寫 .pyc、log 即時輸出
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 先裝相依套件 (psycopg[binary] 已含編譯好的驅動,免額外系統套件),善用 layer 快取
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製應用程式 (app.py + static/)
COPY . .

# 連線字串:預設指向 docker compose 中的 postgres 服務,可於執行時覆寫
ENV DATABASE_URL=postgresql://postgres:postgres@postgres:5432/user_management_demo

EXPOSE 8080

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
