"""
CLI test runner for the AnalystIQ agent.

Use this to verify the agent works end-to-end before building the UI.
Lets you see exactly what SQL was generated, what results came back,
and what explanation was produced — at every step.

Run with: python run.py
"""

import json
from agent import graph


INITIAL_STATE = {
    "question": "",
    "schema": "",
    "sql": "",
    "result": "",
    "error": "",
    "explanation": "",
    "retry_count": 0,
}

DIVIDER = "─" * 50


def main():
    print("\nAnalystIQ — Agent CLI")
    print(DIVIDER)
    print("Try questions like:")
    print("  • How many fraud transactions happened this month?")
    print("  • Which merchant category has the highest fraud rate?")
    print("  • Show me the top 5 customers by total transaction amount")
    print(DIVIDER)

    question = input("\nYour question: ").strip()
    if not question:
        print("No question entered. Exiting.")
        return

    print("\nRunning agent...\n")

    result_state = graph.invoke({**INITIAL_STATE, "question": question})

    print(DIVIDER)
    print("SQL GENERATED")
    print(DIVIDER)
    print(result_state["sql"])

    if result_state.get("retry_count", 0) > 0:
        print(f"\n(Self-corrected {result_state['retry_count']} time(s))")

    print(f"\n{DIVIDER}")
    print("RESULTS")
    print(DIVIDER)

    if result_state.get("error") and not result_state.get("result"):
        print(f"Failed after retries: {result_state['error']}")
    else:
        data = json.loads(result_state.get("result", "[]"))
        print(f"{len(data)} rows returned. Showing first 5:\n")
        for row in data[:5]:
            print(f"  {row}")

    print(f"\n{DIVIDER}")
    print("EXPLANATION")
    print(DIVIDER)
    print(result_state["explanation"])
    print()


if __name__ == "__main__":
    main()
