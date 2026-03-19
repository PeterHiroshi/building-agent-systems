"""
Simple Chatbot -- Augmented LLM Pattern

The simplest agent: a single model call with tools. No loops, no orchestration.
Start here and only add complexity when this fails.
"""

import json
import anthropic

client = anthropic.Anthropic()
MODEL = "claude-sonnet-4-6-20250514"

# --- System Prompt ---

SYSTEM_PROMPT = """You are a customer support agent for TaskFlow, a project management tool.

## Domain Knowledge
- Free tier: 3 projects, 10 users. Pro tier: unlimited, $12/user/month
- Refund policy: full refund within 30 days, prorated after that
- Support hours: 9am-6pm EST, Monday-Friday

## Decision Criteria
- For billing questions: always verify the account first using lookup_account
- For technical issues: check search_docs first before troubleshooting
- For feature requests: log them with log_feedback, acknowledge the request

## Constraints
- Never share internal pricing strategies or roadmap details
- Never process refunds without verifying the account first
- If unsure, escalate rather than guess"""

# --- Tools ---

tools = [
    {
        "name": "lookup_account",
        "description": (
            "Look up a customer account by email address. "
            "Use when: customer asks about their account, billing, or subscription. "
            "Do NOT use when: question is general (not account-specific).\n\n"
            "Example: lookup_account(email='alice@example.com')"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "email": {
                    "type": "string",
                    "description": "Customer email address",
                }
            },
            "required": ["email"],
        },
    },
    {
        "name": "search_docs",
        "description": (
            "Search the product documentation for answers to technical questions. "
            "Use when: customer has a how-to question or technical issue. "
            "Do NOT use when: question is about billing or account status."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query describing the issue",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "log_feedback",
        "description": (
            "Log customer feedback, feature requests, or bug reports. "
            "Use when: customer suggests a feature or reports a bug. "
            "Do NOT use when: customer needs immediate help (solve first, log after)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": ["feature_request", "bug_report", "general_feedback"],
                },
                "description": {"type": "string"},
                "customer_email": {
                    "type": "string",
                    "description": "Optional: customer email for follow-up",
                },
            },
            "required": ["type", "description"],
        },
    },
    {
        "name": "escalate_to_human",
        "description": (
            "Escalate to a human support agent. "
            "Use when: you cannot resolve after 2 attempts, OR customer explicitly requests a human. "
            "Do NOT use when: the issue is straightforward and resolvable."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {"type": "string"},
                "priority": {"type": "string", "enum": ["low", "medium", "high"]},
            },
            "required": ["reason", "priority"],
        },
    },
]


# --- Mock tool implementations ---


def execute_tool(name: str, input_data: dict) -> str:
    """Execute a tool call with mock data. Replace with real implementations."""
    if name == "lookup_account":
        return json.dumps(
            {
                "found": True,
                "email": input_data["email"],
                "plan": "pro",
                "users": 8,
                "next_billing_date": "2025-04-01",
                "account_created": "2024-06-15",
                "status": "active",
            }
        )
    elif name == "search_docs":
        return json.dumps(
            {
                "results": [
                    {
                        "title": "Inviting Team Members",
                        "snippet": "Go to Settings > Team > Invite. Enter email addresses separated by commas.",
                        "url": "https://docs.taskflow.com/team/invite",
                    }
                ]
            }
        )
    elif name == "log_feedback":
        return json.dumps(
            {"logged": True, "ticket_id": "FB-2025-0342", "message": "Feedback recorded."}
        )
    elif name == "escalate_to_human":
        return json.dumps(
            {"escalated": True, "queue_position": 3, "estimated_wait": "5 minutes"}
        )
    return json.dumps({"error": f"Unknown tool: {name}"})


# --- Agent loop ---


def run_agent(user_message: str, max_turns: int = 10) -> str:
    """Run the chatbot agent with tool use loop."""
    messages = [{"role": "user", "content": user_message}]

    for _ in range(max_turns):
        response = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            tools=tools,
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            return "".join(
                block.text for block in response.content if block.type == "text"
            )

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result = execute_tool(block.name, block.input)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    }
                )

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

    return "Max turns reached."


if __name__ == "__main__":
    print("TaskFlow Support Agent (type 'quit' to exit)")
    print("-" * 50)
    while True:
        user_input = input("\nYou: ").strip()
        if user_input.lower() in ("quit", "exit", "q"):
            break
        print(f"\nAgent: {run_agent(user_input)}")
