"""
Support Router — Router Pattern

Routes customer support requests to specialized handlers.
Each handler has its own tools and system prompt, keeping context focused.

Key design decisions:
- Haiku for classification (fast, cheap — classification is a simple task)
- Sonnet for handlers (good enough for focused, tool-using tasks)
- Each handler only loads its relevant tools (prevents tool confusion)
"""

import anthropic
import json
import sys

client = anthropic.Anthropic()

# --- Tool Definitions (per handler) ---

BILLING_TOOLS = [
    {
        "name": "lookup_invoice",
        "description": (
            "Look up a customer's invoice by date range or invoice ID. "
            "Use when: customer asks about charges, billing, or payments.\n"
            "Example: lookup_invoice(customer_email='john@example.com', month='2024-01')"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_email": {"type": "string"},
                "month": {
                    "type": "string",
                    "description": "Month in YYYY-MM format",
                },
                "invoice_id": {"type": "string"},
            },
            "required": ["customer_email"],
        },
    },
    {
        "name": "process_refund",
        "description": (
            "Process a refund for a specific charge. "
            "IMPORTANT: Verify eligibility with lookup_invoice first.\n"
            "Example: process_refund(invoice_id='inv_001', amount=29.99, reason='duplicate_charge')"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "invoice_id": {"type": "string"},
                "amount": {"type": "number"},
                "reason": {
                    "type": "string",
                    "enum": [
                        "duplicate_charge",
                        "service_issue",
                        "cancellation",
                        "other",
                    ],
                },
            },
            "required": ["invoice_id", "amount", "reason"],
        },
    },
]

TECHNICAL_TOOLS = [
    {
        "name": "check_service_status",
        "description": (
            "Check the current status of a service or feature. "
            "Use when: customer reports something not working.\n"
            "Example: check_service_status(service='api')"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "service": {
                    "type": "string",
                    "enum": ["api", "dashboard", "auth", "storage", "all"],
                }
            },
            "required": ["service"],
        },
    },
    {
        "name": "search_knowledge_base",
        "description": (
            "Search the technical knowledge base for solutions. "
            "Use when: you need to find troubleshooting steps or documentation.\n"
            "Example: search_knowledge_base(query='API rate limit errors')"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
            },
            "required": ["query"],
        },
    },
]

ACCOUNT_TOOLS = [
    {
        "name": "get_account_info",
        "description": (
            "Retrieve account details for a customer. "
            "Use when: customer asks about their plan, settings, or account status.\n"
            "Example: get_account_info(email='jane@example.com')"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "email": {"type": "string"},
            },
            "required": ["email"],
        },
    },
    {
        "name": "update_account",
        "description": (
            "Update account settings or plan. "
            "IMPORTANT: Confirm changes with the customer before applying.\n"
            "Example: update_account(email='jane@example.com', plan='professional')"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "email": {"type": "string"},
                "plan": {
                    "type": "string",
                    "enum": ["starter", "professional", "enterprise"],
                },
                "setting": {"type": "string"},
                "value": {"type": "string"},
            },
            "required": ["email"],
        },
    },
]

# --- Handler System Prompts ---

HANDLER_PROMPTS = {
    "billing": """You are a billing support specialist. Help customers with charges, invoices, refunds, and payment issues.

Rules:
- Always look up the invoice before processing a refund
- Confirm the refund amount and reason with the customer
- For duplicate charges, process refund immediately after verification
- For other issues, explain the charge before offering a refund""",
    "technical": """You are a technical support specialist. Help customers with product issues, bugs, and how-to questions.

Rules:
- Check service status first if the customer reports an outage
- Search the knowledge base before giving troubleshooting steps
- If the issue requires engineering, tell the customer you'll escalate
- Provide clear, step-by-step instructions""",
    "account": """You are an account management specialist. Help customers with their account settings, plan changes, and access issues.

Rules:
- Verify the customer's identity before making account changes
- Explain the differences between plans when asked
- Confirm all changes before applying them
- For cancellations, understand the reason and offer alternatives if appropriate""",
    "general": """You are a friendly customer support representative. Help with general questions about our product and company.

Rules:
- Be helpful and friendly
- If the question is about billing, technical issues, or account management, let the customer know you'll connect them with a specialist
- For general questions, provide clear and concise answers""",
}

# --- Mock Tool Implementations ---


def mock_tool(name: str, input_data: dict) -> str:
    """Mock tool execution for demonstration."""
    mocks = {
        "lookup_invoice": {
            "invoices": [
                {
                    "id": "inv_001",
                    "date": "2024-01-15",
                    "amount": 29.99,
                    "status": "paid",
                },
                {
                    "id": "inv_002",
                    "date": "2024-01-15",
                    "amount": 29.99,
                    "status": "paid",
                    "note": "Duplicate charge detected",
                },
            ]
        },
        "process_refund": {
            "status": "processed",
            "refund_id": "ref_001",
            "amount": input_data.get("amount", 0),
        },
        "check_service_status": {
            "service": input_data.get("service", "all"),
            "status": "operational",
            "last_incident": "2024-01-10",
        },
        "search_knowledge_base": {
            "results": [
                {
                    "title": f"How to resolve: {input_data.get('query', '')}",
                    "steps": ["Step 1: Check configuration", "Step 2: Clear cache", "Step 3: Retry"],
                }
            ]
        },
        "get_account_info": {
            "email": input_data.get("email", ""),
            "plan": "professional",
            "status": "active",
            "created": "2023-06-01",
        },
        "update_account": {
            "status": "updated",
            "changes": input_data,
        },
    }
    return json.dumps(mocks.get(name, {"error": f"Unknown tool: {name}"}))


# --- Router ---


def classify_request(request: str) -> str:
    """Classify a customer request using Haiku (fast, cheap)."""
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=20,
        messages=[
            {
                "role": "user",
                "content": f"""Classify this customer support request into exactly one category.
Categories: billing, technical, account, general

Request: {request}

Respond with just the category name, nothing else.""",
            }
        ],
    )
    category = response.content[0].text.strip().lower()

    # Validate classification
    valid = {"billing", "technical", "account", "general"}
    return category if category in valid else "general"


def handle_request(request: str, category: str) -> str:
    """Handle a request with the appropriate specialist."""
    tools_map = {
        "billing": BILLING_TOOLS,
        "technical": TECHNICAL_TOOLS,
        "account": ACCOUNT_TOOLS,
        "general": [],
    }

    tools = tools_map.get(category, [])
    system_prompt = HANDLER_PROMPTS.get(category, HANDLER_PROMPTS["general"])

    messages = [{"role": "user", "content": request}]

    # Agent loop
    for _ in range(10):
        response = client.messages.create(
            model="claude-sonnet-4-6-20250514",
            max_tokens=1024,
            system=system_prompt,
            tools=tools if tools else None,
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            text_blocks = [b for b in response.content if b.type == "text"]
            return text_blocks[0].text if text_blocks else "I'm sorry, I couldn't help with that."

        # Handle tool calls
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result = mock_tool(block.name, block.input)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    }
                )

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

    return "I apologize, but I'm having trouble resolving this. Let me escalate to a human agent."


def support_router(request: str) -> dict:
    """Route and handle a customer support request."""
    print(f"Customer: {request}\n")

    # Step 1: Classify (Haiku — fast and cheap)
    category = classify_request(request)
    print(f"Routed to: {category}\n")

    # Step 2: Handle with specialist (Sonnet — capable)
    response = handle_request(request, category)

    return {"category": category, "response": response}


if __name__ == "__main__":
    request = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "I was charged twice for my subscription last month"
    )
    result = support_router(request)

    print("=" * 60)
    print(f"Category: {result['category']}")
    print("=" * 60)
    print(result["response"])
