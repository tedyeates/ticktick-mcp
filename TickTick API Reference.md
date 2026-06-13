# TickTick API & SDK Reference

## V1 Open API

Official REST API. Base URL: `https://api.ticktick.com/open/v1`

**Developer Portal:** https://developer.ticktick.com

### OAuth 2.0 Setup

1. Register app at developer.ticktick.com
2. Set redirect URI (e.g. `http://localhost:8080/callback`)
3. Get Client ID + Client Secret

| URL | Value |
|-----|-------|
| Auth | `https://ticktick.com/oauth/authorize` |
| Token | `https://ticktick.com/oauth/token` |
| Scopes | `tasks:read`, `tasks:write` |

### Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/project` | GET | List all projects |
| `/project/{id}/data` | GET | Get project with all tasks |
| `/task` | POST | Create task |
| `/task/{id}` | POST | Update task |
| `/project/{pid}/task/{tid}/complete` | POST | Complete task |
| `/task/{pid}/{tid}` | DELETE | Delete task |

### Task Object

```json
{
  "title": "Task title",
  "content": "Description/notes",
  "projectId": "project-id",
  "dueDate": "2026-06-12T12:00:00+0000",
  "priority": 0,
  "tags": ["tag1", "tag2"]
}
```

### Priority Values

| Value | Meaning |
|-------|---------|
| 0 | None |
| 1 | Low |
| 3 | Medium |
| 5 | High |

No 2 or 4 — that's TickTick's design.

### Limitations

No access to: tags management, completed tasks, project folders, habits, batch operations, inbox.

---

## V2 API (Undocumented)

Used by TickTickSync and the web app. Discovered via network inspection.

### Additional Capabilities over V1

- Tags CRUD
- Project folders
- Completed/archived tasks
- Batch operations (create/update/delete multiple in one request)
- Habits and pomodoro timers
- Full task properties (all fields the web app exposes)

### How to Explore

1. Open TickTick web app
2. Browser DevTools → Network tab
3. Perform actions, observe API calls
4. Base URL pattern: `https://api.ticktick.com/api/v2/...`

---

## Python Clients

| Client | V1 | V2 | Maintained | Notes |
|--------|----|----|------------|-------|
| [pyticktick](https://github.com/sebpretzer/pyticktick) | ✅ | ✅ | ✅ | **Recommended.** Pydantic models, good docs |
| [dida365](https://github.com/cyfine/TickTick-Dida365-API-Client) | ✅ | ❌ | ✅ | V1 only, async support |
| [tickthon](https://github.com/anggelomos/tickthon) | ❌ | ✅ | ⚠️ | No documentation |
| [ticktick-py](https://github.com/lazeroffmichael/ticktick-py) | ⚠️ | ⚠️ | ❌ | Abandoned, auth errors |

### pyticktick Quick Start

```python
from pyticktick import TickTickClient

client = TickTickClient(
    client_id="YOUR_CLIENT_ID",
    client_secret="YOUR_CLIENT_SECRET",
    redirect_uri="http://localhost:8080/callback"
)

# After OAuth flow
projects = client.get_projects()
client.create_task(title="Test", project_id=projects[0].id)
```

---

## MCP Servers (AI Agent Integration)

| Server | API | Notes |
|--------|-----|-------|
| [ticktick-mcp](https://github.com/jacepark12/ticktick-mcp) | V1 | Basic CRUD |
| [ticktick-mcp-server](https://github.com/alexarevalo9/ticktick-mcp-server) | V1 | Basic CRUD |

---

## Obsidian Plugins

| Plugin | What it does |
|--------|-------------|
| **TickTickSync** | Bidirectional task sync, V2 API, our primary integration |
| Task Hub | Read-only TickTick task viewer |
| TickTick Today | Shows today's tasks in sidebar |

---

## OAuth Flow (for scripting)

```
1. User visits: https://ticktick.com/oauth/authorize?client_id=X&scope=tasks:read+tasks:write&redirect_uri=Y&response_type=code
2. User grants access → redirected to Y?code=AUTH_CODE
3. Exchange code for token:
   POST https://ticktick.com/oauth/token
   Body: grant_type=authorization_code&code=AUTH_CODE&redirect_uri=Y
   Auth: Basic base64(client_id:client_secret)
4. Response: { "access_token": "...", "token_type": "bearer" }
5. Use token: Authorization: Bearer ACCESS_TOKEN
```
