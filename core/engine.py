# core/engine.py
import json
import os
import re
from typing import Dict, Any

from core.utils import logger
from core.config_loader import load_workspace_config
from core.state_backend import get_state_backend
from core.lock_backend import get_lock_backend
from deploy.repo_manager import RepoManager


def _slugify(name: str) -> str:
    """
    Convert project name into a git-repo-friendly slug.
    """
    slug = name.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "llm-project"


def run_pipeline(mode: str = "generator", workspace_path: str = "workspace.yaml") -> Dict[str, Any]:
    """
    Main orchestrator for the LLM-Ops generator.

    mode:
      - "generator": create/update GitHub repo using templates, maintain state.
      - other modes are reserved; this repo only implements generator mode.
    """
    cfg = load_workspace_config(workspace_path)
    project_name = cfg["project_name"]
    project_slug = _slugify(project_name)

    logger.info("Running LLM-Ops pipeline in mode='%s' for project='%s'", mode, project_name)

    if mode != "generator":
        logger.info("Only 'generator' mode is implemented in this repository.")
        outputs = {"mode": mode, "project_name": project_name}
        with open("pipeline_output.json", "w", encoding="utf-8") as f:
            json.dump(outputs, f, indent=2)
        return outputs

    # Backends
    state_backend = get_state_backend()
    lock_backend = get_lock_backend()
    repo_manager = RepoManager()

    acquired = lock_backend.acquire()
    if not acquired:
        raise RuntimeError("Unable to acquire generator lock; aborting.")

    try:
        state = state_backend.load_state()
        state.setdefault("projects", {})

        project_state: Dict[str, Any] = state["projects"].get(project_name, {})

        # Expected repo name: Infoservices-<slug>-llm
        repo_name = project_state.get("repo_name") or f"Infoservices-{project_slug}-llm"

        logger.info("Target repository for project '%s' is '%s'", project_name, repo_name)

        # Ensure repo exists
        repo_info = repo_manager.ensure_repo(
            repo_name=repo_name,
            description=cfg.get("description") or f"LLM project for {project_name}",
            private=True,
        )

        # Push templates from templates_folder
        templates_dir = cfg.get("templates_folder", "templates")
        repo_manager.push_templates(repo_name, templates_dir)

        # Update state
        project_state.update(
            {
                "project_name": project_name,
                "repo_name": repo_name,
                "repo_full_name": repo_info.get("full_name"),
                "repo_html_url": repo_info.get("html_url"),
                "observability_enabled": bool(cfg.get("observability", {}).get("enabled", True)),
            }
        )
        state["projects"][project_name] = project_state
        state_backend.save_state(state)

        outputs = {
            "mode": "generator",
            "project_name": project_name,
            "repo_name": repo_name,
            "repo_full_name": repo_info.get("full_name"),
            "repo_html_url": repo_info.get("html_url"),
        }

        with open("pipeline_output.json", "w", encoding="utf-8") as f:
            json.dump(outputs, f, indent=2)

        logger.info("Generator pipeline completed successfully: %s", json.dumps(outputs))
        return outputs

    finally:
        lock_backend.release()
