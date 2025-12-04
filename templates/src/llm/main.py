# src/llm/main.py
from llm.agent.payroll_agent import PayrollAgent


def run() -> None:
    """
    Simple runner to exercise the agent. This is not the provision workflow.
    """
    agent = PayrollAgent()
    user_input = "Sample payroll question"
    answer = agent.run(user_input)
    print("Agent answer:", answer)


if __name__ == "__main__":
    run()
