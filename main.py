# main.py
from core.engine import run_pipeline

if __name__ == "__main__":
    # Default: run in generator mode using workspace.yaml
    run_pipeline(mode="generator", workspace_path="workspace.yaml")
