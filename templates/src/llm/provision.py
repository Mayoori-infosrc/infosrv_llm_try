# src/llm/provision.py
import os
from typing import Any, Dict

import yaml

try:
    from info_llm_observe import register
except ImportError:
    def register(project_name: str, tool: str = "phoenix"):
        print(f"[info-llm-observe stub] register(project_name={project_name}, tool={tool})")
        class StubClient:
            def send_test_trace(self) -> Dict[str, Any]:
                print("[info-llm-observe stub] send_test_trace()")
                return {"status": "stub", "project_name": project_name}
        return StubClient()


def run_provision(workspace_path: str = "workspace.yaml") -> Dict[str, Any]:
    """
    Provision pipeline INSIDE the generated repo.

    Responsibilities:
      - Read project_name from workspace.yaml.
      - Call info-llm-observe.register().
      - Send a test trace to validate observability wiring.
    """
    if not os.path.exists(workspace_path):
        raise FileNotFoundError(f"workspace file not found: {workspace_path}")

    with open(workspace_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    project_name = cfg.get("project_name")
    if not project_name:
        raise ValueError("workspace.yaml in generated repo must contain project_name")

    client = register(project_name=project_name, tool=os.getenv("LLM_OBSERVE_TOOL", "phoenix"))

    # The concrete implementation of send_test_trace will live in your wrapper.
    result = getattr(client, "send_test_trace", lambda: {"status": "no-op"})()

    print(f"Provisioned observability for project '{project_name}'. Result: {result}")
    return {"project_name": project_name, "wrapper_result": result}


if __name__ == "__main__":
    run_provision()
