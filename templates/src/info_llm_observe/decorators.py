import time
import uuid
from functools import wraps
from typing import Optional, Any, Dict

from info_llm_observe.registry import get_client
from info_llm_observe.utils import now_seconds, naive_token_estimate, cost_estimate


def instrument(operation: str = "llm-operation", user_id_getter: Optional[callable] = None):
    """
    Decorator to instrument a call.

    Parameters:
      - operation: friendly operation name (e.g., "chat", "vector-search")
      - user_id_getter: optional callable to derive a user id from args/kwargs

    The decorator will:
      - measure time
      - estimate tokens & cost (naive)
      - call provider.send_trace(...) with a structured payload
    """

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            client = get_client()

            start = now_seconds()
            session_id = str(uuid.uuid4())
            try:
                result = fn(*args, **kwargs)
                exc = None
                success = True
            except Exception as e:
                result = None
                exc = e
                success = False
            end = now_seconds()
            duration = round(end - start, 6)

            # input and output textual forms
            try:
                input_text = kwargs.get("prompt") if "prompt" in kwargs else (args[0] if args else "")
            except Exception:
                input_text = str(args) + str(kwargs)
            output_text = str(result) if result is not None else (str(exc) if exc else "")

            tokens = naive_token_estimate(str(input_text)) + naive_token_estimate(output_text)
            cost = cost_estimate(tokens)

            # user id resolution
            user_id = None
            if callable(user_id_getter):
                try:
                    user_id = user_id_getter(*args, **kwargs)
                except Exception:
                    user_id = "unknown"
            else:
                user_id = kwargs.get("user_id") or (args[1] if len(args) > 1 else "unknown")

            payload: Dict[str, Any] = {
                "trace_id": str(uuid.uuid4()),
                "session_id": session_id,
                "user_id": user_id,
                "operation": operation,
                "input": str(input_text),
                "output": output_text,
                "tokens": tokens,
                "cost": cost,
                "duration": duration,
                "success": success,
                "metadata": {},
            }

            # send trace (best effort)
            try:
                client.send_trace(payload)
            except Exception:
                # swallowing provider errors to avoid breaking user's app
                pass

            if exc:
                # re-raise the original exception after recording
                raise exc
            return result

        return wrapper

    return decorator
