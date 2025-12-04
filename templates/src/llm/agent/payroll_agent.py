# src/llm/agent/payroll_agent.py
import os

from .base_agent import BaseAgent

try:
    from info_llm_observe import register, instrument
except ImportError:
    # Fallback for local development if the package is not available yet.
    def register(project_name: str, tool: str = "phoenix"):
        print(f"[info-llm-observe stub] register(project_name={project_name}, tool={tool})")
        return None

    def instrument(operation: str = "llm-call", project: str = None):
        def decorator(fn):
            def wrapper(*args, **kwargs):
                print(f"[info-llm-observe stub] instrument(operation={operation}, project={project})")
                return fn(*args, **kwargs)
            return wrapper
        return decorator


PROJECT_NAME = os.getenv("LLM_OBSERVE_PROJECT_NAME", "REPLACE_PROJECT_NAME")
OBS_TOOL = os.getenv("LLM_OBSERVE_TOOL", "phoenix")

# Register this application with the observability wrapper (no-op in stub mode).
register(project_name=PROJECT_NAME, tool=OBS_TOOL)


class PayrollAgent(BaseAgent):
    """
    Example agent. In real usage, this will call your LLM provider.
    """

    def __init__(self):
        prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts", "system_prompt.yaml")
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                self.system_prompt = f.read()
        except Exception:
            self.system_prompt = ""

    @instrument(operation="payroll-chat", project=PROJECT_NAME)
    def run(self, user_input: str) -> str:
        # Placeholder implementation. Replace with actual LLM call.
        return f"[PAYROLL DEMO] You asked: '{user_input}'. This is a dummy response."
