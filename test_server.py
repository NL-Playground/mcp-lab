"""
demo-mcp 本地檢查 — FastMCP in-memory Client(不需 pytest)

FastMCP 慣用法:把 server 物件直接交給 Client,
在記憶體內呼叫工具。本檔是一支可直接執行的腳本,用 print 看結果:

    python test_server.py

分兩段:
  1. 能力盤點:列出 tools / resources / prompts 與唯讀標註(免外部服務)。
  2. 實際呼叫:call_tool 打到 demo-app;demo-app 未啟動時會自動略過。
     (預設連 http://localhost:8080,可用 DEMO_APP_URL 覆寫)
"""
import asyncio

from fastmcp import Client

import server


async def show_capabilities(c: Client) -> None:
    print("=== 1. 能力盤點 ===")
    tools = await c.list_tools()
    print(f"工具 ({len(tools)}):")
    for t in tools:
        ro = t.annotations.readOnlyHint if t.annotations else None
        kind = "唯讀" if ro else "寫入"
        print(f"  - {t.name:18} [{kind}]")

    tmpl = await c.list_resource_templates()
    res = await c.list_resources()
    prompts = await c.list_prompts()
    print("資源:", [str(r.uri) for r in res], "+ 模板:", [t.uriTemplate for t in tmpl])
    print("Prompt:", [p.name for p in prompts])


async def call_tools(c: Client) -> None:
    print("\n=== 2. 實際呼叫(需要 demo-app)===")
    try:
        users = (await c.call_tool("list_users", {})).data
        print(f"list_users -> {len(users)} 位使用者,第一位:{users[0]['email']}")

        ok = (await c.call_tool(
            "verify_login", {"email": "alice@demo.local", "password": "Admin@123"}
        )).data
        print("verify_login(alice, 正確密碼) ->", ok)

        bad = (await c.call_tool(
            "verify_login", {"email": "alice@demo.local", "password": "wrong"}
        )).data
        print("verify_login(alice, 錯誤密碼) ->", bad)
    except Exception as e:
        print(f"(略過)呼叫失敗,demo-app 可能未啟動:{e}")


async def main() -> None:
    # in-memory:把 server 物件交給 Client
    async with Client(server.mcp) as c:
        await show_capabilities(c)
        await call_tools(c)


if __name__ == "__main__":
    asyncio.run(main())
