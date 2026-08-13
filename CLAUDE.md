# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A learning lab for the **Model Context Protocol (MCP)**, built around a toy "user management"
system. Two labs, in increasing complexity:

- **LAB-1-DBHub** (`docker-compose.lab1.yml`) — Postgres only, explored directly via the
  [DBHub](https://github.com/bytebase/dbhub) MCP server (stdio, configured in VS Code Copilot,
  not part of this repo's code).
- **LAB-2-FastMCP** (`docker-compose.lab2.yml`, this repo's main content) — wraps `demo-app`
  (a small FastAPI web app) with a hand-written **FastMCP** server (`server.py`) so an AI
  client can call it as MCP tools/resources/prompts over HTTP.

Docs for each lab live in `LAB-docs/LAB-1-DBHub/` and `LAB-docs/LAB-2-FastMCP/` (both in
Chinese) — read these first for the intended teaching narrative before changing behavior.

## Architecture

Connection chain: **AI Client → demo-mcp (`server.py`) → demo-app (`demo-app/app.py`) → demo-db (Postgres)**

- `server.py` is a thin HTTP wrapper: it does **not** talk to Postgres directly. Every tool
  proxies to `demo-app`'s REST API via a module-level `DemoAppClient` (httpx, cookie-session
  based, lazy login, auto re-login once on 401).
- `demo-app/app.py` (FastAPI) is the only thing that talks to Postgres, and only ever calls
  **existing DB functions/views** — it contains no business logic of its own:
  `fn_verify_login`, `fn_create_user`, `fn_set_user_active`, `fn_change_user_role`,
  `fn_change_password`, `v_users`, `audit_log`. Auth is a simple in-memory session-token dict
  (`SESSIONS`), not for production use.
- `demo-db/init/*.sql` runs once, in filename order, only when the Postgres data volume is
  empty (Postgres `docker-entrypoint-initdb.d` behavior): `01_schema.sql` (tables + `v_users`
  view), `02_seed.sql` (roles/departments/demo users), `03_procedures.sql` (`audit_log` +
  the `fn_*` management functions). To re-run after editing these, you must drop the volume
  (see below) — restarting the container alone will not re-seed.
- `server.py` tools are split into read-only (`readOnlyHint: True`) queries and side-effecting
  writes (`destructiveHint`/`idempotentHint` set per tool), matching MCP annotation
  conventions — preserve these annotations accurately when adding tools. It also exposes
  MCP **resources** (`audit://recent`, `user://{email}`) and **prompts**
  (`permission_distribution_review`, `review_user_access`) alongside the tools — see
  `LAB-docs/LAB-2-FastMCP/02-FastMCP.md` for the full tool/resource/prompt table and the
  Tool vs Resource vs Prompt distinction this lab is teaching.
- Networking convention: services always **bind** `0.0.0.0`; connection **targets** use the
  compose service name (`postgres`, `demo-app`), never `localhost`, since demo-mcp and
  demo-app run in separate containers. `DEMO_APP_URL` defaults to `localhost:8080` for local
  (non-Docker) runs of `server.py` but is overridden to `http://demo-app:8080` in
  `docker-compose.lab2.yml` and in the `Dockerfile`.

## Environment variables (server.py / demo-mcp)

| Variable | Purpose | Default |
|---|---|---|
| `DEMO_APP_URL` | demo-app base URL | `http://localhost:8080` |
| `DEMO_APP_EMAIL` / `DEMO_APP_PASSWORD` | admin account demo-mcp logs in as to perform writes | `alice@demo.local` / `Admin@123` |
| `MCP_HOST` / `MCP_PORT` | HTTP transport bind address | `0.0.0.0` / `8000` |

demo-app reads `DATABASE_URL` (defaults to
`postgresql://postgres:postgres@localhost:5432/user_management_demo`).

Demo accounts (seeded in `02_seed.sql`): `alice@demo.local` / `Admin@123` (admin),
`bob@demo.local` / `Write@123` (write), `carol@demo.local` / `Read@123` (read).

## Common commands

Run everything (Postgres + demo-app + demo-mcp) via Docker:

```bash
docker compose -f docker-compose.lab2.yml up -d --build
docker compose -f docker-compose.lab2.yml ps
docker compose -f docker-compose.lab2.yml logs -f demo-mcp
docker compose -f docker-compose.lab2.yml down          # stop (keeps data volume)
docker compose -f docker-compose.lab2.yml down -v        # stop and wipe DB (forces re-seed)
```

LAB-1 only needs Postgres: `docker compose -f docker-compose.lab1.yml up -d`.

Run demo-app locally against a Dockerized Postgres (see `.claude/launch.json` for the
equivalent debug config):

```bash
docker compose -f docker-compose.lab2.yml up -d postgres
pip install -r demo-app/requirements.txt
cd demo-app && uvicorn app:app --reload --port 8080
```

Run demo-mcp (`server.py`) locally against a running demo-app:

```bash
pip install -r requirements.txt
DEMO_APP_URL=http://localhost:8080 python server.py    # serves http://localhost:8000/mcp
```

Check demo-mcp's capabilities and exercise it end-to-end — this is the project's only test
entry point (there is no pytest suite despite the `test_` filename):

```bash
DEMO_APP_URL=http://localhost:8080 python test_server.py
```

It uses FastMCP's in-memory `Client(server.mcp)` — part 1 (capability listing: tools,
resources, prompts, readOnly annotations) needs no external services; part 2 (actual tool
calls) needs demo-app running and is skipped automatically if it isn't.

Interactive inspection of the MCP server:

```bash
fastmcp dev inspector server.py
```

Copilot/VS Code MCP integration is configured in `.vscode/mcp.json` (points at
`http://localhost:8000/mcp`).
