# src/llm/agent/base_agent.py

class BaseAgent:
    """
    Base class for all LLM agents in the generated project.
    """

    def run(self, text: str) -> str:
        raise NotImplementedError("Agent must implement run()")
