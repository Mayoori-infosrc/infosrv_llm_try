# deploy/agent_scaffolder.py

MAIN_PY = """from llm.agent.payroll_agent import PayrollAgent


def handler(event=None, context=None):
    agent = PayrollAgent()
    user_input = (event or {}).get("user_input", "Hello")

    response = agent.run(user_input)
    return {"answer": response}


if __name__ == "__main__":
    print(handler({"user_input": "Test payroll question"})["answer"])
"""

DOCKERFILE_TEMPLATE = """FROM python:3.10
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
ENV PYTHONPATH=/app/src
CMD ["python", "-m", "llm.main"]
"""

README_TEMPLATE = """# Auto-generated LLM Agent

This repository was created automatically by the LLM-Ops framework.

It includes:
- Base agent structure (under src/llm/agent)
- Prompt folder (under src/llm/prompts)
- Hooks for observability (via info-llm-observe)
- Dockerfile
- src/llm/main.py runner
"""
