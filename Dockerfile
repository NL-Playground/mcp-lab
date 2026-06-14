# demo-mcp — 把 demo-app 包成 MCP Server (FastMCP, HTTP transport)
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py .
COPY test_server.py .

ENV MCP_HOST=0.0.0.0 \
    MCP_PORT=8000 \
    DEMO_APP_URL=http://demo-app:8080

EXPOSE 8000

CMD ["python", "server.py"]
