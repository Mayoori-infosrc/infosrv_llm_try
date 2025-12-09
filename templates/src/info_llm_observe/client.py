# optional high-level client helpers; not required but convenient.
from typing import Any, Dict
from info_llm_observe.registry import get_client


class ObservabilityClient:
    def __init__(self):
        self._provider = get_client()

    def send_test_trace(self) -> Dict[str, Any]:
        return self._provider.send_test_trace()

    def send_trace(self, trace_payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._provider.send_trace(trace_payload)
