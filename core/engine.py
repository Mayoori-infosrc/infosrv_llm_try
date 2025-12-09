# core/engine.py
import json
import os
import re
from typing import Dict, Any

import yaml

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

    # Prefer environment override (usually set by the GitHub Action input)
    project_name = os.getenv("LLMOPS_PROJECT_NAME")
    if not project_name:
        raise ValueError("LLMOPS_PROJECT_NAME not provided from GitHub Action.")
    project_slug = _slugify(project_name)

    logger.info("Running LLM-Ops pipeline in mode='%s' for project='%s'", mode, project_name)

    if mode != "generator":
        logger.info("Only 'generator' mode is implemented in this repository.")
        outputs = {"mode": mode, "project_name": project_name}
        with open("pipeline_output.json", "w", encoding="utf-8") as f:
            json.dump(outputs, f, indent=2)
        return outputs

    # Backends + repo manager
    state_backend = get_state_backend()
    lock_backend = get_lock_backend()
    # RepoManager reads env vars if token/owner not provided, but allow passing explicitly
    repo_manager = RepoManager()

    acquired = lock_backend.acquire()
    if not acquired:
        raise RuntimeError("Unable to acquire generator lock; aborting.")

    try:
        # Load state and ensure structure
        state = state_backend.load_state() or {}
        state.setdefault("projects", {})

        project_state: Dict[str, Any] = state["projects"].get(project_name, {})

        # Compute repo name (slugified)
        repo_name = project_state.get("repo_name") or f"Infoservices-{project_slug}-llm"
        logger.info("Target repository for project '%s' is '%s'", project_name, repo_name)

        # Ensure repository exists (create if absent)
        repo_info = repo_manager.ensure_repo(
            repo_name=repo_name,
            description=cfg.get("description") or f"LLM project for {project_name}",
            private=True,
        )
        logger.info("Repository ready: %s", repo_info.get("html_url"))

        # Push template files
        templates_dir = cfg.get("templates_folder", "templates")
        repo_manager.push_templates(repo_name, templates_dir)

        # -----------------------------------------------------
        # Sanity check: ensure templates folder contains workflow YAML
        # (helps debug missing workflows in generated repo)
        # -----------------------------------------------------
        templates_workflows_dir = os.path.join(templates_dir, ".github", "workflows")
        if os.path.isdir(templates_workflows_dir):
            found = False
            for root, _dirs, files in os.walk(templates_workflows_dir):
                for f in files:
                    if f.lower().endswith((".yml", ".yaml")):
                        found = True
                        logger.info("Found workflow template: %s", os.path.join(root, f))
            if not found:
                logger.warning("No workflow YAML files found under %s", templates_workflows_dir)
        else:
            logger.warning(
                "Templates did not include a .github/workflows directory at %s",
                templates_workflows_dir,
            )

        # -----------------------------------------------------
        # Inject PHOENIX_BASE_URL secret into the generated repo
        # -----------------------------------------------------
        phoenix_url = os.getenv("PHOENIX_BASE_URL")
        if phoenix_url:
            try:
                repo_manager.add_secret(
                    repo_name=repo_name,
                    secret_name="PHOENIX_BASE_URL",
                    secret_value=phoenix_url,
                )
            except Exception:
                logger.exception("Failed to add PHOENIX_BASE_URL secret to %s", repo_name)
        else:
            logger.warning("PHOENIX_BASE_URL not provided — secret not added.")

        # Build the generated workspace.yaml for the new repo
        provision_workspace = {
            "project_name": project_name,
            "observability": {
                "enabled": cfg.get("observability", {}).get("enabled", True),
                "tool": cfg.get("observability", {}).get("tool", "phoenix"),
            },
            "memory": cfg.get("memory", {"enabled": False}),
            "knowledge": cfg.get("knowledge", {"enabled": False}),
            "mcp": cfg.get("mcp", {"enabled": False}),
        }

        ws_yaml = yaml.safe_dump(provision_workspace, sort_keys=False)

        # Upload the generated workspace.yaml to the repo root
        repo_manager.upload_file(
            repo_name=repo_name,
            path="workspace.yaml",
            content=ws_yaml,
            message="Add generated workspace.yaml",
        )

        # Update and persist state
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
        try:
            lock_backend.release()
        except Exception:
            logger.exception("Error releasing lock; continuing.")
