from typing import Optional, Dict, Any

from info_llm_observe.providers.phoenix_provider import PhoenixProvider
from info_llm_observe.providers.base import ObservabilityProvider

_active_client: Optional[ObservabilityProvider] = None


def register(project_name: str, tool: str = "phoenix", **kwargs) -> ObservabilityProvider:
    """
    Register an observability client. Call at application startup.

    Returns the provider instance (so the caller can call send_test_trace()).

    Example:
        client = register("hr-chat-prod", tool="phoenix")
        client.send_test_trace()
    """
    global _active_client
    tool = (tool or "phoenix").lower()
    if tool == "phoenix":
        base_url = kwargs.pop("base_url", None)
        _active_client = PhoenixProvider(project_name=project_name, base_url=base_url, **kwargs)
    else:
        raise ValueError(f"Unsupported observability tool: {tool}")

    return _active_client


def get_client() -> ObservabilityProvider:
    if _active_client is None:
        raise RuntimeError("Observability client not registered. Call register(...) first.")
    return _active_client
