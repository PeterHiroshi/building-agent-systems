"""
Code Reviewer -- Evaluator-Optimizer Pattern

Reviews code iteratively. The evaluator scores the review and provides
feedback. The reviewer revises until quality thresholds are met.
"""

import json
import anthropic

client = anthropic.Anthropic()
MODEL = "claude-sonnet-4-6-20250514"

REVIEWER_PROMPT = """You are an expert code reviewer. Review code for:
1. Correctness -- Does it do what it should?
2. Security -- Injection, auth, data exposure risks?
3. Performance -- Obvious inefficiencies, N+1 queries?
4. Readability -- Clear to other developers?
5. Edge cases -- Boundary conditions handled?

For each issue: state file/line, severity (critical/warning/suggestion), what's wrong, and how to fix it.
Focus on substantive issues, not style. Limit to the 5 most important. If the code is good, say so."""

EVALUATOR_PROMPT = """Score this code review 1-10 on each dimension:
1. Correctness: Are identified issues real? (no false positives)
2. Completeness: Did it catch the important issues? (no false negatives)
3. Actionability: Can the developer fix each issue from the feedback alone?
4. Prioritization: Are issues ranked by actual severity?

If average < 8, provide specific improvement instructions.

Return JSON:
{"scores": {"correctness": N, "completeness": N, "actionability": N, "prioritization": N}, "average": N, "needs_revision": true/false, "feedback": "specific improvements or empty string"}"""


def review_code(code_diff: str, max_iterations: int = 3) -> dict:
    """Review code with iterative quality improvement."""
    # Generate initial review
    review = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=REVIEWER_PROMPT,
        messages=[{"role": "user", "content": f"Review this code:\n\n```\n{code_diff}\n```"}],
    ).content[0].text

    for iteration in range(max_iterations):
        # Evaluate
        eval_response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=EVALUATOR_PROMPT,
            messages=[{
                "role": "user",
                "content": f"Code:\n```\n{code_diff}\n```\n\nReview:\n{review}",
            }],
        ).content[0].text

        try:
            eval_result = json.loads(eval_response)
        except json.JSONDecodeError:
            return {"review": review, "iterations": iteration + 1, "parse_error": True}

        if not eval_result.get("needs_revision"):
            return {"review": review, "scores": eval_result.get("scores"), "iterations": iteration + 1}

        # Revise
        review = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=REVIEWER_PROMPT,
            messages=[{
                "role": "user",
                "content": (
                    f"Revise your review based on feedback.\n\n"
                    f"Code:\n```\n{code_diff}\n```\n\n"
                    f"Previous review:\n{review}\n\n"
                    f"Feedback: {eval_result['feedback']}"
                ),
            }],
        ).content[0].text

    return {"review": review, "iterations": max_iterations}


SAMPLE = """
def process_payment(user_id, amount):
    user = db.query("SELECT * FROM users WHERE id = " + user_id)
    if user:
        balance = user.balance - amount
        db.execute("UPDATE users SET balance = " + str(balance))
        send_email(user.email, "Payment processed: $" + str(amount))
        return True
    return False
"""

if __name__ == "__main__":
    print("Code Reviewer (Evaluator-Optimizer Pattern)")
    print("=" * 50)
    result = review_code(SAMPLE)
    print(f"Iterations: {result['iterations']}")
    if "scores" in result:
        print(f"Scores: {result['scores']}")
    print(f"\n{result['review']}")
