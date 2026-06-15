"""TickTick MCP Server — secure, controlled access to TickTick for AI agents."""

import json
import os
import sys
import logging
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

# --- Config ---
QUICK_NOTES_PROJECT_ID = os.environ.get("QUICK_NOTES_PROJECT_ID", "")
PROCESSED_PROJECT_ID = os.environ.get("PROCESSED_PROJECT_ID", "")
EXCLUDED_PROJECTS = [p.strip() for p in os.environ.get("EXCLUDED_PROJECTS", "").split(",") if p.strip()]
SHOPPING_PROJECTS = [p.strip() for p in os.environ.get("SHOPPING_PROJECTS", "").split(",") if p.strip()]
DRY_RUN = "--dry-run" in sys.argv
RATE_LIMIT = 50
TAGS_FILE = Path(__file__).parent.parent / "tags.json"
AUDIT_LOG = Path(__file__).parent.parent / "audit.log"

# --- State ---
_op_count = 0

# --- Audit ---
logging.basicConfig(
    filename=str(AUDIT_LOG),
    level=logging.INFO,
    format="%(asctime)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)


def _audit(tool: str, params: dict, result: str = "ok"):
    logging.info(f"{tool} | params={json.dumps(params)} | result={result}")


def _check_rate():
    global _op_count
    _op_count += 1
    if _op_count > RATE_LIMIT:
        raise RuntimeError(f"Rate limit exceeded ({RATE_LIMIT} ops/session)")


def _is_excluded(project_name: str) -> bool:
    return project_name.lower() in [p.lower() for p in EXCLUDED_PROJECTS]


# --- Tags persistence ---
def _load_tags() -> list[str]:
    if TAGS_FILE.exists():
        return json.loads(TAGS_FILE.read_text())
    return []


def _save_tags(tags: list[str]):
    TAGS_FILE.write_text(json.dumps(sorted(set(tags)), indent=2))


# --- MCP Server ---
mcp = FastMCP("ticktick")


@mcp.tool()
def ping() -> str:
    """Health check."""
    _check_rate()
    _audit("ping", {})
    return "pong"


@mcp.tool()
def trigger_auth() -> str:
    """Start OAuth flow — opens browser for user to authorize. Blocks until complete."""
    _check_rate()
    _audit("trigger_auth", {})
    if DRY_RUN:
        return "dry-run: would open browser for OAuth"
    from auth import authorize
    authorize()
    return "Authorization complete. Tokens saved."


@mcp.tool()
def list_projects() -> list[dict]:
    """List all TickTick projects (id + name)."""
    _check_rate()
    _audit("list_projects", {})
    if DRY_RUN:
        return [{"id": "dry-run", "name": "dry-run"}]
    from ticktick import list_projects as _list
    return _list()


@mcp.tool()
def read_quick_notes() -> list[dict]:
    """Read tasks from Quick Notes project only."""
    _check_rate()
    _audit("read_quick_notes", {})
    if not QUICK_NOTES_PROJECT_ID:
        raise ValueError("QUICK_NOTES_PROJECT_ID not configured")
    if DRY_RUN:
        return [{"id": "dry-run", "title": "dry-run note"}]
    from ticktick import get_project_data
    data = get_project_data(QUICK_NOTES_PROJECT_ID)
    return [{"id": t["id"], "title": t["title"]} for t in data.get("tasks", [])]


@mcp.tool()
def create_task(
    title: str,
    project_name: str,
    due_date: str | None = None,
    priority: int = 0,
    tags: list[str] | None = None,
) -> dict:
    """Create a task in an approved project.

    Args:
        title: Task title
        project_name: Target project name (must not be excluded)
        due_date: Optional ISO date string
        priority: 0=none, 1=low, 3=medium, 5=high
        tags: Optional list of tag strings
    """
    _check_rate()
    params = {"title": title, "project_name": project_name, "due_date": due_date, "priority": priority, "tags": tags}
    _audit("create_task", params)

    if _is_excluded(project_name):
        msg = f"Project '{project_name}' is excluded"
        _audit("create_task", params, result=msg)
        raise ValueError(msg)

    if priority not in (0, 1, 3, 5):
        raise ValueError(f"Invalid priority {priority}. Must be 0, 1, 3, or 5")

    if DRY_RUN:
        return {"id": "dry-run", "title": title, "projectId": "dry-run"}

    from ticktick import list_projects as _list, create_task as _create

    # Resolve project name → id
    projects = _list()
    match = next((p for p in projects if p["name"].lower() == project_name.lower()), None)
    if not match:
        raise ValueError(f"Project '{project_name}' not found")

    payload = {"title": title, "projectId": match["id"], "priority": priority}
    if due_date:
        payload["dueDate"] = due_date
    if tags:
        payload["tags"] = tags
        # Update local tags
        all_tags = _load_tags()
        all_tags.extend(tags)
        _save_tags(all_tags)

    return _create(payload)


@mcp.tool()
def list_tags() -> list[str]:
    """Return known tags so AI uses existing ones."""
    _check_rate()
    _audit("list_tags", {})
    return _load_tags()


@mcp.tool()
def move_to_processed(task_id: str) -> dict:
    """Move a Quick Note to the Processed project after triage.

    Args:
        task_id: ID of task in Quick Notes to move
    """
    _check_rate()
    _audit("move_to_processed", {"task_id": task_id})

    if not QUICK_NOTES_PROJECT_ID or not PROCESSED_PROJECT_ID:
        raise ValueError("QUICK_NOTES_PROJECT_ID and PROCESSED_PROJECT_ID must be configured")

    if DRY_RUN:
        return {"id": task_id, "projectId": PROCESSED_PROJECT_ID}

    from ticktick import get_task, delete_task, create_task as _create

    # Validate task belongs to Quick Notes
    task = get_task(QUICK_NOTES_PROJECT_ID, task_id)
    if task.get("projectId") != QUICK_NOTES_PROJECT_ID:
        raise ValueError("Task does not belong to Quick Notes project")

    # Recreate in Processed then delete from Quick Notes
    payload = {
        "title": task["title"],
        "projectId": PROCESSED_PROJECT_ID,
        "priority": task.get("priority", 0),
    }
    if task.get("content"):
        payload["content"] = task["content"]
    if task.get("tags"):
        payload["tags"] = task["tags"]
    if task.get("dueDate"):
        payload["dueDate"] = task["dueDate"]

    new_task = _create(payload)
    delete_task(QUICK_NOTES_PROJECT_ID, task_id)
    return new_task


@mcp.tool()
def clear_shopping_list(shop: str | None = None) -> str:
    """Delete all tasks from shopping project(s).

    Args:
        shop: Optional shop name to clear (e.g. "Lidl"). Clears all if omitted.
    """
    _check_rate()
    _audit("clear_shopping_list", {"shop": shop})

    if not SHOPPING_PROJECTS:
        raise ValueError("SHOPPING_PROJECTS not configured")

    if shop and shop.lower() not in [p.lower() for p in SHOPPING_PROJECTS]:
        raise ValueError(f"'{shop}' is not a configured shopping project")

    targets = [shop] if shop else SHOPPING_PROJECTS

    if DRY_RUN:
        return f"dry-run: would clear {targets}"

    from ticktick import list_projects as _list, get_project_data, delete_task

    projects = _list()
    deleted = 0
    for target in targets:
        match = next((p for p in projects if p["name"].lower() == target.lower()), None)
        if not match:
            continue
        data = get_project_data(match["id"])
        for task in data.get("tasks", []):
            delete_task(match["id"], task["id"])
            deleted += 1

    return f"Cleared {deleted} tasks from {targets}"


@mcp.tool()
def create_shopping_list(items: list[dict]) -> str:
    """Create shopping list tasks in TickTick, routed to shop projects.

    Args:
        items: List of {title, project_name, sort_order}. Title includes emoji+quantity.
    """
    _check_rate()
    _audit("create_shopping_list", {"count": len(items)})

    if not items:
        raise ValueError("No items provided")

    if DRY_RUN:
        return f"dry-run: would create {len(items)} tasks"

    from ticktick import list_projects as _list, create_task as _create

    projects = _list()
    created = 0
    for item in items:
        title = item["title"]
        project_name = item["project_name"]
        sort_order = item.get("sort_order", 0)

        match = next((p for p in projects if p["name"].lower() == project_name.lower()), None)
        if not match:
            raise ValueError(f"Shopping project '{project_name}' not found")

        payload = {"title": title, "projectId": match["id"], "sortOrder": sort_order}
        _create(payload)
        created += 1

    return f"Created {created} shopping tasks"


@mcp.tool()
def add_shopping_item(title: str, project_name: str, sort_order: int = 0) -> dict:
    """Add a single item to a shopping project without clearing existing items.

    Args:
        title: Item title with emoji+quantity (e.g. "🥬 Carrots — 3")
        project_name: Shop project name (e.g. "Lidl", "Asian Supermarket")
        sort_order: Aisle position for ordering (lower = higher in list)
    """
    _check_rate()
    params = {"title": title, "project_name": project_name, "sort_order": sort_order}
    _audit("add_shopping_item", params)

    if not SHOPPING_PROJECTS:
        raise ValueError("SHOPPING_PROJECTS not configured")
    if project_name.lower() not in [p.lower() for p in SHOPPING_PROJECTS]:
        raise ValueError(f"'{project_name}' is not a configured shopping project")

    if DRY_RUN:
        return {"id": "dry-run", "title": title, "projectId": "dry-run"}

    from ticktick import list_projects as _list, create_task as _create

    projects = _list()
    match = next((p for p in projects if p["name"].lower() == project_name.lower()), None)
    if not match:
        raise ValueError(f"Shopping project '{project_name}' not found")

    payload = {"title": title, "projectId": match["id"], "sortOrder": sort_order}
    return _create(payload)


@mcp.tool()
def read_shopping_list(shop: str | None = None) -> list[dict]:
    """Read tasks from shopping project(s).

    Args:
        shop: Optional shop name to read (e.g. "Lidl"). Reads all if omitted.
    """
    _check_rate()
    _audit("read_shopping_list", {"shop": shop})

    if not SHOPPING_PROJECTS:
        raise ValueError("SHOPPING_PROJECTS not configured")

    if shop and shop.lower() not in [p.lower() for p in SHOPPING_PROJECTS]:
        raise ValueError(f"'{shop}' is not a configured shopping project")

    targets = [shop] if shop else SHOPPING_PROJECTS

    if DRY_RUN:
        return [{"id": "dry-run", "title": "dry-run item", "shop": targets[0], "sort_order": 0}]

    from datetime import datetime, timedelta
    from ticktick import list_projects as _list, get_project_data, get_completed_tasks

    projects = _list()
    results = []
    now = datetime.utcnow()
    from_date = (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S+0000")
    to_date = now.strftime("%Y-%m-%dT%H:%M:%S+0000")

    matched = []
    for target in targets:
        match = next((p for p in projects if p["name"].lower() == target.lower()), None)
        if not match:
            continue
        matched.append(match)
        data = get_project_data(match["id"])
        for task in data.get("tasks", []):
            results.append({
                "id": task["id"],
                "title": task["title"],
                "shop": match["name"],
                "sort_order": task.get("sortOrder", 0),
                "completed": False,
            })

    if matched:
        try:
            project_ids = [m["id"] for m in matched]
            completed = get_completed_tasks(project_ids, from_date, to_date)
            for task in completed:
                shop_name = next((m["name"] for m in matched if m["id"] == task.get("projectId")), targets[0])
                results.append({
                    "id": task["id"],
                    "title": task["title"],
                    "shop": shop_name,
                    "sort_order": task.get("sortOrder", 0),
                    "completed": True,
                })
        except Exception:
            pass

    results.sort(key=lambda x: (x["shop"], x["completed"], x["sort_order"]))
    return results


@mcp.tool()
def remove_shopping_item(title: str, project_name: str | None = None) -> str:
    """Remove a single item from a shopping project by title match.

    Args:
        title: Item title to search for (case-insensitive substring match)
        project_name: Optional shop to search in. Searches all shopping projects if omitted.
    """
    _check_rate()
    params = {"title": title, "project_name": project_name}
    _audit("remove_shopping_item", params)

    if not SHOPPING_PROJECTS:
        raise ValueError("SHOPPING_PROJECTS not configured")

    if project_name and project_name.lower() not in [p.lower() for p in SHOPPING_PROJECTS]:
        raise ValueError(f"'{project_name}' is not a configured shopping project")

    targets = [project_name] if project_name else SHOPPING_PROJECTS

    if DRY_RUN:
        return f"dry-run: would remove '{title}' from {targets}"

    from ticktick import list_projects as _list, get_project_data, delete_task

    projects = _list()
    search = title.lower()
    for target in targets:
        match = next((p for p in projects if p["name"].lower() == target.lower()), None)
        if not match:
            continue
        data = get_project_data(match["id"])
        for task in data.get("tasks", []):
            if search in task["title"].lower():
                delete_task(match["id"], task["id"])
                return f"Removed '{task['title']}' from {target}"

    return f"No item matching '{title}' found in {targets}"


if __name__ == "__main__":
    mcp.run()
