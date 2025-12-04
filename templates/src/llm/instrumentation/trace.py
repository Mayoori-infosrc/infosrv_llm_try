# src/llm/instrumentation/trace.py
import os
import uuid
from typing import Any, Dict, List, Optional

import requests

PHOENIX_BASE = os.getenv("PHOENIX_BASE_URL", "").rstrip("/")
HEADERS = {"Content-Type": "application/json"}


def send_trace(
    project_id: str,
    user_id: str,
    session_id: str,
    messages: List[Dict[str, Any]],
    model: str,
    tokens: int,
    cost: float,
    extra: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Low-level helper to push a single trace directly to Phoenix.

    In the long term, this logic should live inside the `info-llm-observe` wrapper.
    """
    if not PHOENIX_BASE:
        print("PHOENIX_BASE_URL not set; skipping trace")
        return None

    trace_id = str(uuid.uuid4())
    payload = {
        "trace_id": trace_id,
        "session_id": session_id,
        "user_id": user_id,
        "messages": messages,
        "model": model,
        "tokens": tokens,
        "cost": cost,
        "metadata": extra or {},
    }

    url = f"{PHOENIX_BASE}/v1/projects/{project_id}/traces"
    try:
        resp = requests.post(url, headers=HEADERS, json=payload, timeout=5)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print("send_trace failed:", e)
        return None
