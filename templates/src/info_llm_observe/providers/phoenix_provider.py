import os
import uuid
import requests
from typing import Any, Dict, Optional
from datetime import datetime, timezone, timedelta

from info_llm_observe.providers.base import ObservabilityProvider


class PhoenixProvider(ObservabilityProvider):
    """
    Phoenix Observability Provider (correct schema)
    """

    def __init__(self, project_name: str, base_url: Optional[str] = None, timeout: int = 10):
        self.project_name = project_name
        self.base = (base_url or os.getenv("PHOENIX_BASE_URL", "")).rstrip("/")

        if not self.base:
            raise RuntimeError("PHOENIX_BASE_URL must be set.")

        self.timeout = timeout
        self.headers = {"Content-Type": "application/json"}

        # Resolve Phoenix project_id
        self.project_id = self.ensure_project()

    # ---------------------------
    # HTTP helpers
    # ---------------------------
    def _get(self, path: str):
        resp = requests.get(f"{self.base}{path}", headers=self.headers, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, payload: Dict[str, Any]):
        resp = requests.post(f"{self.base}{path}", headers=self.headers, json=payload, timeout=self.timeout)
        try:
            resp.raise_for_status()
        except requests.HTTPError as e:
            # Surface validation errors (JSON if available, otherwise text)
            body = None
            try:
                body = resp.json()
            except Exception:
                body = resp.text
            raise RuntimeError(f"HTTP {resp.status_code} {resp.reason} for {resp.url}: {body}") from e
        if resp.text:
            try:
                return resp.json()
            except Exception:
                return {"raw": resp.text}
        return {}

    # ---------------------------
    # PROJECT MANAGEMENT
    # ---------------------------
    def ensure_project(self) -> str:
        # Try to find an existing project by name
        try:
            resp = self._get("/v1/projects")
            # API may return { "data": [...] } or a bare list
            projects = resp.get("data", resp) if isinstance(resp, dict) else resp

            if isinstance(projects, list):
                for p in projects:
                    if p.get("name") == self.project_name:
                        return p.get("id")
        except Exception:
            # ignore and attempt to create
            pass

        created = self._post(
            "/v1/projects",
            {"name": self.project_name, "description": f"Project {self.project_name} created by llm-ops"}
        )

        data = created.get("data", created)
        pid = data.get("id") if isinstance(data, dict) else None

        if not pid:
            raise RuntimeError(f"Phoenix project creation failed: {created}")

        return pid

    # ---------------------------
    # SEND TRACE (adapter function)
    # ---------------------------
    def send_trace(self, trace_payload: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        span = {
            "span_id": str(uuid.uuid4()),
            "trace_id": trace_payload.get("trace_id", str(uuid.uuid4())),
            "name": trace_payload.get("operation", "trace"),
            "span_kind": trace_payload.get("span_kind", "SPAN_KIND_INTERNAL"),
            "status_code": trace_payload.get("status_code", "STATUS_CODE_OK"),
            # Use RFC3339 timestamps with milliseconds and 'Z' for UTC
            "start_time": now.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "end_time": (now + timedelta(seconds=1)).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "attributes": trace_payload
        }
        return self.send_span(span)

    # ---------------------------
    # SEND SPAN (CORRECT PAYLOAD)
    # ---------------------------
    def send_span(self, span: Dict[str, Any]) -> Dict[str, Any]:
        # Phoenix expects "data" to be a list where each item has span fields at top level
        # Required fields: name, context, span_kind, start_time, end_time, status_code
        span_data = {
            "name": span.get("name", "unknown"),
            "context": {
                "trace_id": span.get("trace_id", str(uuid.uuid4())),
                "span_id": span.get("span_id", str(uuid.uuid4())),
            },
            "span_kind": span.get("span_kind", "SPAN_KIND_INTERNAL"),
            "start_time": span.get("start_time"),
            "end_time": span.get("end_time"),
            "status_code": span.get("status_code", "STATUS_CODE_OK"),
            "attributes": span.get("attributes", {}),
            "queries": [],
            "spans": [],
        }
        
        payload = {
            "data": [span_data]
        }

        path = f"/v1/projects/{self.project_id}/spans"
        return self._post(path, payload)

    # ---------------------------
    # TEST TRACE FOR PROVISION
    # ---------------------------
    def send_test_trace(self) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        span = {
            "span_id": str(uuid.uuid4()),
            "trace_id": str(uuid.uuid4()),
            "name": "provision-test",
            "span_kind": "SPAN_KIND_INTERNAL",
            "status_code": "STATUS_CODE_OK",
            "start_time": now.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "end_time": (now + timedelta(seconds=1)).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "attributes": {
                "input": "ping",
                "output": "pong",
                "source": "llmops-provision",
                "tokens": 1,
                "duration": 0.1,
                "cost": 0.0
            }
        }
        return self.send_span(span)
