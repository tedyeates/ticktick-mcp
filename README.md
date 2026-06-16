# TickTick MCP Server

Secure MCP server giving AI agents controlled access to TickTick.

## Setup

1. Copy `.env.example` to `.env` and fill in credentials
2. Run OAuth flow: `uv run python src/auth.py`
3. Start server: `uv run python src/server.py`

## Tools

| Tool | Description |
|------|-------------|
| `ping` | Health check |
| `trigger_auth` | Start OAuth flow in browser |
| `list_projects` | List all projects (id + name) |
| `list_tags` | Return known tags |
| `read_quick_notes` | Read tasks from Quick Notes only |
| `create_task` | Create task in approved project |
| `move_to_processed` | Move Quick Note to Processed project |
| `read_shopping_list` | Read tasks from shopping projects (includes completed items) |
| `get_completed_today` | Get all tasks completed today (excludes shopping; for diary) |
| `create_shopping_list` | Batch-create shopping list tasks |
| `add_shopping_item` | Add single item to a shopping project |
| `remove_shopping_item` | Remove item from shopping project by title match |
| `clear_shopping_list` | Delete all tasks from shopping project(s) |

## Flags

- `--dry-run` — logs operations without calling TickTick API

## Security

- Project excludelist prevents writes to protected projects
- Rate limit: 50 ops per session
- Audit log written to `audit.log`
- No file reading, code access, or arbitrary API tools exposed
