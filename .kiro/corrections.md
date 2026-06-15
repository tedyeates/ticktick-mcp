# Corrections Log

- ❌ `from src.ticktick import ...` in server.py → ✅ `from ticktick import ...` (server runs from `src/` dir via sys.path; `src.` prefix breaks MCP runtime)
- ❌ `from src.auth import ...` in server.py → ✅ `from auth import ...` (same reason)
- ❌ `POST /open/v1/task/{id}` with changed `projectId` to move task → ✅ TickTick Open API silently ignores projectId changes; must delete+recreate to move between projects
- ❌ `update_task` calling `resp.json()` unconditionally → ✅ Check `resp.content` first, return fallback dict if empty (API returns empty body on update)
- ❌ `uv` not recognized in VS Code/Kiro terminal → ✅ PATH cached at editor launch time; must fully restart editor after installing uv (reload window insufficient)
- ❌ Attempting to read `.env` file → ✅ Never read `.env`; contains secrets. If config seems wrong, ask user to check and restart MCP server.
