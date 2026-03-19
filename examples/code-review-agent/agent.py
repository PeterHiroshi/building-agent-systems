"""
Code Review Agent — Evaluator-Optimizer Pattern

Reviews code in two passes:
1. Generator: writes an initial code review
2. Evaluator: checks if the review covers security, edge cases, and conventions
3. Generator: revises the review based on evaluator feedback

Includes the think tool for structured reasoning during review.
"""

import anthropic
import json
import sys
from pathlib import Path

client = anthropic.Anthropic()
MODEL = "claude-sonnet-4-6-20250514"

# --- Think Tool ---

think_tool = {
    "name": "think",
    "description": (
        "Use this to reason about the code before writing your review. "
        "Think about: What does this code do? What could go wrong? "
        "Are there security issues? Edge cases? Your thoughts are private."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "thought": {
                "type": "string",
                "description": "Your reasoning about the code",
            }
        },
        "required": ["thought"],
    },
}


REVIEWER_PROMPT = """You are an expert code reviewer. Review code for:
1. Bugs and logic errors
2. Security vulnerabilities (injection, XSS, auth issues)
3. Edge cases (null inputs, empty arrays, boundary conditions)
4. Code quality (readability, naming, duplication)
5. Performance concerns

Use the think tool to reason about the code before writing your review.

Format your review as:
## Summary
[1-2 sentence overview]

## Issues Found
[Numbered list, each with severity: critical/warning/suggestion]

## What's Good
[Positive observations]

## Recommendations
[Specific improvement suggestions]"""

EVALUATOR_PROMPT = """You are a code review evaluator. Your job is to check if a code review is thorough.

Check these dimensions (score 1-5 each):
1. Security: Did the review check for injection, auth issues, data validation?
2. Edge cases: Did it consider null inputs, empty collections, boundary values?
3. Logic: Did it trace the main code paths for correctness?
4. Specificity: Are the findings specific (line numbers, concrete fixes) or vague?
5. Completeness: Did it cover all the code, or skip sections?

If average score < 4, provide specific feedback on what the review missed.

Return JSON:
{"scores": {"security": N, "edge_cases": N, "logic": N, "specificity": N, "completeness": N}, "average": N, "feedback": "...", "needs_revision": bool}"""


def run_with_think_tool(system_prompt: str, user_message: str) -> str:
    """Run an LLM call with the think tool, handling the tool loop."""
    messages = [{"role": "user", "content": user_message}]

    for _ in range(5):
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=system_prompt,
            tools=[think_tool],
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            text_blocks = [b for b in response.content if b.type == "text"]
            return text_blocks[0].text if text_blocks else ""

        # Handle think tool calls
        tool_results = []
        for block in response.content:
            if block.type == "tool_use" and block.name == "think":
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps({"status": "ok"}),
                    }
                )

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

    return ""


def generate_review(code: str, feedback: str | None = None) -> str:
    """Generate (or revise) a code review."""
    if feedback:
        prompt = f"""Revise your code review based on this feedback.

Feedback on your previous review:
{feedback}

Code being reviewed:
```
{code}
```

Address all feedback points in your revised review."""
    else:
        prompt = f"""Review this code thoroughly.

```
{code}
```"""

    return run_with_think_tool(REVIEWER_PROMPT, prompt)


def evaluate_review(code: str, review: str) -> dict:
    """Evaluate a code review for thoroughness."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=EVALUATOR_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"""Evaluate this code review.

Code that was reviewed:
```
{code}
```

Review:
{review}""",
            }
        ],
    )

    try:
        return json.loads(response.content[0].text)
    except json.JSONDecodeError:
        return {"scores": {}, "average": 5, "feedback": "", "needs_revision": False}


def code_review_agent(code: str, max_iterations: int = 2) -> dict:
    """
    Review code using the evaluator-optimizer pattern.

    Returns:
        dict with 'review', 'iterations', 'final_scores'
    """
    print("Generating initial review...\n")
    review = generate_review(code)

    for i in range(max_iterations):
        print(f"Evaluating review (iteration {i + 1})...")
        evaluation = evaluate_review(code, review)

        print(f"  Average score: {evaluation.get('average', 'N/A')}/5")
        if evaluation.get("scores"):
            for dim, score in evaluation["scores"].items():
                print(f"  - {dim}: {score}/5")

        if not evaluation.get("needs_revision", False):
            print(f"\nReview passed evaluation after {i + 1} iteration(s).\n")
            return {
                "review": review,
                "iterations": i + 1,
                "final_scores": evaluation.get("scores", {}),
            }

        print(f"  Revising based on feedback: {evaluation.get('feedback', '')[:100]}...\n")
        review = generate_review(code, feedback=evaluation.get("feedback", ""))

    return {
        "review": review,
        "iterations": max_iterations,
        "final_scores": evaluation.get("scores", {}),
    }


# --- Example Code to Review ---

EXAMPLE_CODE = '''
def process_payment(user_id, amount, card_number):
    """Process a payment for a user."""
    user = db.query(f"SELECT * FROM users WHERE id = {user_id}")
    if user:
        if amount > 0:
            result = payment_gateway.charge(card_number, amount)
            db.query(f"INSERT INTO transactions (user_id, amount) VALUES ({user_id}, {amount})")
            return {"status": "success", "transaction_id": result.id}
    return {"status": "failed"}
'''

if __name__ == "__main__":
    if len(sys.argv) > 1:
        code = Path(sys.argv[1]).read_text()
    else:
        print("No file provided, using example code with intentional issues.\n")
        code = EXAMPLE_CODE

    result = code_review_agent(code)

    print("=" * 60)
    print("FINAL CODE REVIEW")
    print("=" * 60)
    print(result["review"])
    print(f"\nCompleted in {result['iterations']} iteration(s)")
