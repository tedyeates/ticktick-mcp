# TickTick MCP Server — Implementation Plan

## Problem Statement

Build a secure Python MCP server that gives an AI agent controlled access to TickTick. The AI must never read the server code or credentials. Only specific, safe operations are exposed.

## Security Constraints

- AI can only run the server, never read source or credentials
- Allowed operations: read Quick Notes, create tasks (with tags), list projects, list tags, move notes to Processed
- NO delete, NO update, NO reading from arbitrary lists
- All write operations validated against a project excludelist (all projects allowed by default, specific ones blocked)
- Credentials stored outside the AI's accessible filesystem

## Architecture

```mermaid
flowchart TD
    A["AI Agent (Kiro CLI)"] -->|"MCP stdio"| B["ticktick-mcp-server"]
    B -->|"OAuth V1 API"| C["TickTick API"]
    D[".env"] -->|"credentials"| B

    subgraph "Exposed Tools"
        T1["read_quick_notes"]
        T2["create_task"]
        T3["move_to_processed"]
        T4["list_projects"]
        T5["list_tags"]
    end
```

## Tech Stack

- Python 3.10+
- `mcp[cli]` SDK (FastMCP, stdio transport)
- `httpx` for HTTP calls
- `pydantic` for schemas
- `python-dotenv` for credentials
- `uv` as package manager
- One-command startup: `uv run python src/server.py`

## Environment Variables (.env)

```
TICKTICK_CLIENT_ID=
TICKTICK_CLIENT_SECRET=
TICKTICK_ACCESS_TOKEN=
TICKTICK_REFRESH_TOKEN=
QUICK_NOTES_PROJECT_ID=
PROCESSED_PROJECT_ID=
EXCLUDED_PROJECTS=
```

## Task Breakdown

### Task 1: Project scaffolding and ping tool

**Objective:** Create project structure with a working MCP server that responds to ping.

**Implementation:**
- `uv init`, add dependencies: `mcp[cli]`, `httpx`, `pydantic`, `python-dotenv`
- Create `src/server.py` with `FastMCP("ticktick")` and a `ping` tool
- Add `.env.example` with all required variables
- Add README with one-command run instruction

**Test:** Run `uv run mcp dev src/server.py`, call `ping`, get "pong".

**Demo:** Server starts with one command, responds via MCP inspector.

---

### Task 2: OAuth authentication module

**Objective:** Handle OAuth token storage, refresh, and initial authorization flow.

**Implementation:**
- Create `src/auth.py` — loads `.env`, stores tokens in local `tokens.json`
- One-time CLI command: `uv run python src/auth.py` opens browser for OAuth
- Token refresh on expiry using `httpx`
- Auth URL: `https://ticktick.com/oauth/authorize`
- Token URL: `https://ticktick.com/oauth/token`
- Scopes: `tasks:read`, `tasks:write`

**Test:** Run auth flow → tokens saved → subsequent runs use stored token.

**Demo:** `uv run python src/auth.py` → browser → authorize → tokens saved.

---

### Task 3: `list_projects` tool

**Objective:** Read-only tool returning all TickTick projects (id + name).

**Implementation:**
- Create `src/ticktick.py` — thin API client wrapping `httpx` calls to `https://api.ticktick.com/open/v1/project`
- Expose via `@mcp.tool()` in `server.py`
- Return list of `{id, name}` objects

**Test:** Call via MCP inspector, confirm real projects appear.

**Demo:** AI sees all available project names and IDs.

---

### Task 4: `read_quick_notes` tool

**Objective:** Read tasks from the Quick Notes project only.

**Implementation:**
- Use `QUICK_NOTES_PROJECT_ID` from env
- Call `/project/{id}/data` endpoint
- Return task titles + IDs only
- Refuse requests for any other project

**Test:** Add a note in TickTick Quick Notes, call tool, confirm it appears.

**Demo:** AI sees exactly what's in Quick Notes, nothing else.

---

### Task 5: `create_task` tool

**Objective:** Create tasks in approved projects with metadata.

**Parameters:**
- `title` (required) — string
- `project_name` (required) — string, must not be in EXCLUDED_PROJECTS
- `due_date` (optional) — ISO date string
- `priority` (optional) — 0/1/3/5
- `tags` (optional) — list of strings

**Implementation:**
- Resolve project name to ID using cached project list
- Validate project is NOT in excludelist, reject otherwise
- POST to `/task` endpoint
- Update local `tags.json` if new tags are used

**Test:** Create task via inspector, confirm in TickTick with correct project/tags.

**Demo:** Create "Make CV more beautiful" in project "cv" with tag "career".

---

### Task 6: `list_tags` tool

**Objective:** Return existing tags so AI uses them rather than inventing new ones.

**Implementation:**
- Maintain `tags.json` in server directory
- Updated automatically when `create_task` uses a new tag
- Seed manually or from initial task scan on first run
- Return sorted list of tag strings

**Test:** Call tool, see tags. Create task with new tag, call again, see it added.

**Demo:** AI sees ["career", "social", "health"] and picks from existing.

---

### Task 7: `move_to_processed` tool

**Objective:** Move a Quick Note to the Processed project after triage.

**Parameters:**
- `task_id` (required) — string

**Implementation:**
- Validate task belongs to Quick Notes project (fetch and check `projectId`)
- POST update changing `projectId` to `PROCESSED_PROJECT_ID`
- Reject if task isn't from Quick Notes

**Test:** Create quick note, move via tool, confirm in Processed project.

**Demo:** After triage, "Make CV beautiful" moves from Quick Notes → Processed.

---

---

## TickTick V1 API Reference (httpx calls)

Base URL: `https://api.ticktick.com/open/v1`
Auth header: `Authorization: Bearer {access_token}`

### OAuth Flow

1. Redirect user: `https://ticktick.com/oauth/authorize?client_id=X&scope=tasks:read+tasks:write&redirect_uri=Y&response_type=code`
2. User grants access → redirected to `Y?code=AUTH_CODE`
3. Exchange code: `POST https://ticktick.com/oauth/token`
   - Body: `grant_type=authorization_code&code=AUTH_CODE&redirect_uri=Y`
   - Auth: `Basic base64(client_id:client_secret)`
   - Response: `{ "access_token": "...", "token_type": "bearer" }`

No documented refresh token mechanism in V1 — token appears long-lived. Re-auth if expired.

### Endpoints Used

| Endpoint | Method | Used by | Request Body | Response |
|----------|--------|---------|-------------|----------|
| `/project` | GET | `list_projects` | — | `[{id, name, color, sort_order, view_mode, kind}, ...]` |
| `/project/{id}/data` | GET | `read_quick_notes` | — | `{project: {...}, tasks: [{id, project_id, title, content, due_date, priority, tags, status, ...}], columns: []}` |
| `/task` | POST | `create_task` | `{title, projectId, content, dueDate, priority, tags, timeZone}` | created task object |
| `/task/{id}` | POST | `move_to_processed` | `{projectId: NEW_ID}` (partial update) | updated task object |
| `/project/{pid}/task/{tid}` | GET | validate in `move_to_processed` | — | task object |

### Task Object Shape (V1 response)

```json
{
  "id": "67ec273212e1101e875f078b",
  "projectId": "67ec23b18f08cf38dd957e10",
  "title": "Task title",
  "content": "Description/notes",
  "desc": "",
  "dueDate": "2026-06-12T12:00:00+0000",
  "priority": 0,
  "tags": ["tag1", "tag2"],
  "status": 0,
  "isAllDay": false,
  "startDate": null,
  "timeZone": "Europe/London",
  "sortOrder": -4398046511104,
  "kind": "TEXT"
}
```

### Priority Values

| Value | Meaning |
|-------|---------|
| 0 | None |
| 1 | Low |
| 3 | Medium |
| 5 | High |

### V1 API Limitations (relevant to this project)

- **No tags endpoint** — V1 has no way to list/manage tags
- No access to completed tasks
- No batch operations
- `POST /task/{id}` for update accepts partial body (only fields to change)

### Tags: V2 Undocumented API

Since V1 has no tag listing, use V2 `GET /batch/check/0` (undocumented).

- Base URL: `https://api.ticktick.com/api/v2`
- Auth: Login via `POST /user/signon` with `{username, password}` → get cookie/token
- Response from `/batch/check/0` includes `"tags": [{label, color, parent, ...}, ...]`

**Alternative (simpler):** Maintain `tags.json` locally, seeded manually. Updated when `create_task` uses new tags. Avoids V2 auth complexity entirely.

**Decision:** Use `tags.json` approach. V2 auth requires storing plaintext password and reverse-engineering login flow. Not worth complexity for tag listing. Seed file manually, auto-append on task creation.

---

### Task 8: Security hardening

**Objective:** Enforce security boundaries regardless of what the AI requests.

**Implementation:**
- Excludelist validation on all write operations (all projects allowed unless explicitly excluded)
- Audit log (`audit.log`) for all operations with timestamp + parameters
- Rate limiting: max 50 operations per session
- `--dry-run` flag for testing (logs without calling TickTick)
- No tool exposes file reading, code access, or arbitrary API calls
- Graceful error messages (no stack traces or credential leaks)

**Test:** Create task in excluded project → rejected. Check audit log after session.

**Demo:** Audit log shows full session history. Excluded project operations fail gracefully.
