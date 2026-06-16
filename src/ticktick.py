"""Thin TickTick API client."""

import httpx
from auth import get_access_token

BASE_URL = "https://api.ticktick.com/open/v1"


def _headers() -> dict:
    return {"Authorization": f"Bearer {get_access_token()}"}


def list_projects() -> list[dict]:
    resp = httpx.get(f"{BASE_URL}/project", headers=_headers())
    resp.raise_for_status()
    return [{"id": p["id"], "name": p["name"]} for p in resp.json()]


def get_project_data(project_id: str) -> dict:
    resp = httpx.get(f"{BASE_URL}/project/{project_id}/data", headers=_headers())
    resp.raise_for_status()
    return resp.json()


def create_task(payload: dict) -> dict:
    resp = httpx.post(f"{BASE_URL}/task", json=payload, headers=_headers())
    resp.raise_for_status()
    return resp.json()


def get_task(project_id: str, task_id: str) -> dict:
    resp = httpx.get(f"{BASE_URL}/project/{project_id}/task/{task_id}", headers=_headers())
    resp.raise_for_status()
    return resp.json()


def update_task(task_id: str, payload: dict) -> dict:
    resp = httpx.post(f"{BASE_URL}/task/{task_id}", json=payload, headers=_headers())
    resp.raise_for_status()
    if resp.content:
        return resp.json()
    return {"id": task_id, **payload}



def move_task(from_project_id: str, to_project_id: str, task_id: str) -> dict:
    payload = [{"fromProjectId": from_project_id, "toProjectId": to_project_id, "taskId": task_id}]
    resp = httpx.post(f"{BASE_URL}/task/move", json=payload, headers=_headers())
    resp.raise_for_status()
    return resp.json()[0]


def delete_task(project_id: str, task_id: str):
    resp = httpx.delete(f"{BASE_URL}/project/{project_id}/task/{task_id}", headers=_headers())
    resp.raise_for_status()


def get_completed_tasks(project_ids: list[str], start_date: str, end_date: str) -> list:
    body = {"startDate": start_date, "endDate": end_date}
    if project_ids:
        body["projectIds"] = project_ids
    resp = httpx.post(f"{BASE_URL}/task/completed", json=body, headers=_headers())
    resp.raise_for_status()
    return resp.json()
