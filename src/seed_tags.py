"""Scan all TickTick projects and populate tags.json from existing tasks."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ticktick import list_projects, get_project_data

TAGS_FILE = Path(__file__).parent.parent / "tags.json"

projects = list_projects()
all_tags = set()

for p in projects:
    try:
        data = get_project_data(p["id"])
        for task in data.get("tasks", []):
            for tag in task.get("tags") or []:
                all_tags.add(tag)
    except Exception as e:
        print(f"  Skipped {p['name']}: {e}")

TAGS_FILE.write_text(json.dumps(sorted(all_tags), indent=2))
print(f"Saved {len(all_tags)} tags to {TAGS_FILE}")
