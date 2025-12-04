# providers/observability/phoenix_adapter.py
import os
from typing import Optional, Any, Dict, List

import requests

from providers.observability.interface import ObservabilityInterface


class PhoenixAdapter(ObservabilityInterface):
    """
    Adapter for Phoenix observability HTTP API.

    Environment:
      - PHOENIX_BASE_URL (required)
    """

    def __init__(self, base_url: Optional[str] = None, timeout: int = 10):
        self.base = (base_url or os.getenv("PHOENIX_BASE_URL", "")).rstrip("/")
        if not self.base:
            raise RuntimeError("PHOENIX_BASE_URL must be set")

        self.timeout = timeout
        self.headers = {"Content-Type": "application/json"}

    def _get(self, path: str) -> requests.Response:
        url = f"{self.base}{path}"
        resp = requests.get(url, headers=self.headers, timeout=self.timeout)
        if resp.status_code >= 400:
            raise RuntimeError(f"Phoenix GET {url} failed: {resp.status_code} {resp.text}")
        return resp

    def _post(self, path: str, json_payload: Dict[str, Any]) -> requests.Response:
        url = f"{self.base}{path}"
        resp = requests.post(url, headers=self.headers, json=json_payload, timeout=self.timeout)
        if resp.status_code >= 400:
            raise RuntimeError(f"Phoenix POST {url} failed: {resp.status_code} {resp.text}")
        return resp

    def _delete(self, path: str) -> requests.Response:
        url = f"{self.base}{path}"
        resp = requests.delete(url, headers=self.headers, timeout=self.timeout)
        if resp.status_code >= 400:
            raise RuntimeError(f"Phoenix DELETE {url} failed: {resp.status_code} {resp.text}")
        return resp

    # ---- ObservabilityInterface implementation ----

    def create_project(self, name: str, description: str = "") -> Dict[str, Any]:
        payload = {"name": name, "description": description}
        resp = self._post("/v1/projects", payload)
        body = resp.json()

        data = body.get("data", body) if isinstance(body, dict) else body
        pid = data.get("id") or data.get("project_id")
        if not pid:
            raise RuntimeError(f"Unexpected Phoenix response when creating project: {body}")

        return {
            "project_id": pid,
            "project_url": f"{self.base}/projects/{pid}",
            "raw": data,
        }

    def list_projects(self) -> List[Dict[str, Any]]:
        resp = self._get("/v1/projects")
        body = resp.json()
        data = body.get("data", body) if isinstance(body, dict) else body
        if not isinstance(data, list):
            raise RuntimeError(f"Unexpected Phoenix response for list_projects: {body}")
        return data

    def get_project(self, project_id: str) -> Dict[str, Any]:
        resp = self._get(f"/v1/projects/{project_id}")
        return resp.json()

    def delete_project(self, project_id: str) -> None:
        self._delete(f"/v1/projects/{project_id}")
