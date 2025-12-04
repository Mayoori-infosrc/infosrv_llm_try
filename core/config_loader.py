# core/config_loader.py
import os
from typing import Any, Dict

import yaml

DEFAULT_SCHEMA: Dict[str, Any] = {
    "version": 1,
    "project_name": None,
    "description": "",
    "observability": {"enabled": True, "tool": "phoenix"},
    "mcp": {"enabled": False},
    "knowledge": {"enabled": False},
    "memory": {"enabled": False},
    "prompts_folder": "templates/src/llm/prompts",
    "templates_folder": "templates",
}


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively merge two dicts. Values in `override` take precedence.
    """
    result = dict(base)
    for k, v in override.items():
        if (
            k in result
            and isinstance(result[k], dict)
            and isinstance(v, dict)
        ):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def load_workspace_config(path: str = "workspace.yaml") -> Dict[str, Any]:
    """
    Load workspace.yaml, apply defaults, and return a normalized config dict.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"workspace file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    cfg = _deep_merge(DEFAULT_SCHEMA, raw)

    # Override project_name from environment if provided (for GitHub Action input)
    override_name = os.getenv("LLMOPS_PROJECT_NAME")
    if override_name:
        cfg["project_name"] = override_name

    if not cfg.get("project_name"):
        raise ValueError("workspace.yaml must contain project_name")

    # Normalize observability section
    if isinstance(cfg.get("observability"), bool):
        cfg["observability"] = {
            "enabled": bool(cfg["observability"]),
            "tool": "phoenix",
        }

    return cfg
