# Tool Design Reference

## Why Tool Design Matters

Tools dominate agent context. In a typical agentic conversation, tool definitions and tool call results make up 60-80% of all tokens. A poorly designed tool doesn't just fail — it wastes context budget, confuses the agent, and cascades into wrong decisions downstream.

## The Five Principles

### 1. Merge Granular APIs into Agent-Appropriate Tools

Agents aren't developers. They don't think in terms of REST endpoints. Merge low-level operations into task-oriented tools.

```
BAD (too granular):
  - get_user(user_id)
  - get_user_orders(user_id)
  - get_order_details(order_id)
  - get_order_items(order_id)

GOOD (agent-appropriate):
  - get_user_with_recent_orders(user_identifier)
    Returns: user profile + last 5 orders with items
    Agent makes 1 call instead of 4
```

**Rule of thumb:** If the agent always calls tools A, B, C in sequence, merge them into one tool.

### 2. Design for Agent Affordances

The tool description is the most important part. It tells the agent WHEN to use the tool, not just what it does.

```
BAD:
  "description": "Queries the database"

GOOD:
  "description": "Search for customer records by name, email, or phone number.
   Use this when: you need to look up a customer's account information.
   Do NOT use for: checking order status (use get_order_status instead).
   Example: search_customers({query: 'john@example.com', limit: 5})"
```

### 3. Return Semantic IDs

When your tool returns identifiers, make them human-readable so the agent can reason about them.

```
BAD:  {"id": "a1b2c3d4-e5f6-7890"}
GOOD: {"id": "order_2024_jan_15_john_doe_laptop"}

BAD:  {"status": 3}
GOOD: {"status": "shipped", "status_detail": "In transit, arriving Thursday"}
```

### 4. Errors Must Suggest Next Action

Every error message should tell the agent what to do next. This is the difference between an agent that recovers and one that loops forever.

```
BAD:
  {"error": "Not found"}

GOOD:
  {"error": "No user found with email 'jon@example.com'. Did you mean 'john@example.com'? Try search_users with a partial name match."}

BAD:
  {"error": "Permission denied"}

GOOD:
  {"error": "Cannot access billing data for this user. The user's account is managed by the enterprise team. Use escalate_to_enterprise(user_id, reason) to hand off."}
```

### 5. Pagination and Filtering as Defaults

Agents handle 5-10 results well. They handle 1000 results badly — it fills context and degrades reasoning.

```
GOOD:
  "parameters": {
    "query": {"type": "string", "description": "Search term"},
    "limit": {"type": "integer", "default": 10, "description": "Max results (default: 10, max: 50)"},
    "offset": {"type": "integer", "default": 0},
    "sort_by": {"type": "string", "enum": ["relevance", "date", "name"], "default": "relevance"}
  }
```

---

## Minimal Viable Tool (MVT) Design

Build the smallest tool that lets the agent accomplish the task. Complexity should be added only when evals show the agent struggling.

### MVT Checklist

```
[ ] Does ONE thing well (single responsibility)
[ ] Description explains WHEN to use it, not just what it does
[ ] 1-3 required parameters (keep it simple)
[ ] Optional parameters have sensible defaults
[ ] Error messages include a suggested recovery action
[ ] Returns structured data the agent can reason about
[ ] Has 1-3 usage examples in the description
[ ] Output is < 500 tokens for typical use (stays within context budget)
```

### MVT Design Process

```
1. What task does the agent need to accomplish?
2. What is the minimum information the tool needs to do it?
3. What should the tool return so the agent can reason about the result?
4. What can go wrong, and what should the agent do in each case?
5. Write the tool. Test it. Only add complexity when evals demand it.
```

---

## Error Recovery Patterns

### Pattern 1: Suggest Alternative Action

```python
def search_users(query: str) -> dict:
    results = db.search_users(query)
    if not results:
        return {
            "error": f"No users found matching '{query}'.",
            "suggestion": "Try a broader search term, or use list_recent_users() to browse.",
            "did_you_mean": fuzzy_match(query, get_all_usernames())
        }
    return {"users": results}
```

### Pattern 2: Partial Success with Warnings

```python
def bulk_update_users(updates: list[dict]) -> dict:
    successes = []
    failures = []
    for update in updates:
        try:
            apply_update(update)
            successes.append(update["user_id"])
        except ValidationError as e:
            failures.append({"user_id": update["user_id"], "error": str(e)})

    return {
        "succeeded": len(successes),
        "failed": len(failures),
        "failures": failures,
        "suggestion": "Review failed updates and retry with corrected data." if failures else None
    }
```

### Pattern 3: Graceful Degradation

```python
def get_user_profile(user_id: str) -> dict:
    user = db.get_user(user_id)
    if not user:
        return {"error": f"User '{user_id}' not found. Use search_users to find the correct ID."}

    # Try to enrich, but don't fail if enrichment fails
    profile = {"user": user}
    try:
        profile["recent_orders"] = db.get_recent_orders(user_id, limit=5)
    except Exception:
        profile["recent_orders"] = None
        profile["warning"] = "Could not load recent orders. Order service may be temporarily unavailable."

    return profile
```

---

## Complete Tool Templates

### Template 1: Search Tool

```python
search_tool = {
    "name": "search_products",
    "description": """Search the product catalog by keyword, category, or price range.

Use this when: the user asks about available products, wants to find a specific item, or needs product recommendations.
Do NOT use for: checking order status or inventory levels.

Examples:
- search_products(query="wireless headphones", limit=5)
- search_products(category="electronics", max_price=100, sort_by="rating")""",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search keywords (matched against name and description)"
            },
            "category": {
                "type": "string",
                "description": "Filter by category. Use list_categories() to see available options.",
                "enum": ["electronics", "clothing", "home", "books", "sports"]
            },
            "min_price": {"type": "number", "description": "Minimum price filter"},
            "max_price": {"type": "number", "description": "Maximum price filter"},
            "sort_by": {
                "type": "string",
                "enum": ["relevance", "price_low", "price_high", "rating", "newest"],
                "default": "relevance"
            },
            "limit": {
                "type": "integer",
                "default": 10,
                "description": "Number of results to return (default: 10, max: 50)"
            }
        },
        "required": ["query"]
    }
}
```

### Template 2: Action Tool with Confirmation

```python
refund_tool = {
    "name": "process_refund",
    "description": """Process a refund for a specific order.

Use this when: the customer has requested a refund AND you have verified the order is eligible.
IMPORTANT: Always verify refund eligibility BEFORE calling this tool:
  1. Order must be within 30-day return window
  2. Item must not be in "final sale" category
  3. Customer must have the original order ID

If unsure about eligibility, use check_refund_eligibility(order_id) first.

Example: process_refund(order_id="order_2024_laptop_john", reason="defective", amount=299.99)""",
    "input_schema": {
        "type": "object",
        "properties": {
            "order_id": {
                "type": "string",
                "description": "The order ID to refund (use search_orders to find it)"
            },
            "reason": {
                "type": "string",
                "enum": ["defective", "wrong_item", "changed_mind", "not_as_described", "late_delivery"],
                "description": "Reason for refund"
            },
            "amount": {
                "type": "number",
                "description": "Refund amount in dollars. Must not exceed original order total."
            },
            "partial": {
                "type": "boolean",
                "default": false,
                "description": "True if this is a partial refund"
            }
        },
        "required": ["order_id", "reason", "amount"]
    }
}
```

### Template 3: Read-Only Data Tool

```python
analytics_tool = {
    "name": "get_sales_metrics",
    "description": """Retrieve sales metrics for a given time period.

Use this when: the user asks about sales performance, revenue, or business metrics.
Returns: total revenue, order count, average order value, and top products.

Time periods: Use ISO date format (YYYY-MM-DD). Defaults to last 30 days if not specified.

Example: get_sales_metrics(start_date="2024-01-01", end_date="2024-01-31")""",
    "input_schema": {
        "type": "object",
        "properties": {
            "start_date": {
                "type": "string",
                "description": "Start date in YYYY-MM-DD format (default: 30 days ago)"
            },
            "end_date": {
                "type": "string",
                "description": "End date in YYYY-MM-DD format (default: today)"
            },
            "group_by": {
                "type": "string",
                "enum": ["day", "week", "month"],
                "default": "day",
                "description": "Time granularity for the metrics"
            }
        },
        "required": []
    }
}
```

### Template 4: Multi-Step Composite Tool

```python
onboard_tool = {
    "name": "onboard_new_customer",
    "description": """Create a new customer account with all required setup.

This tool handles the full onboarding flow:
1. Creates the customer record
2. Sets up default preferences
3. Sends welcome email
4. Returns the new customer profile

Use this when: a new customer needs to be set up in the system.
Do NOT use for: updating existing customers (use update_customer instead).

Example: onboard_new_customer(name="Jane Smith", email="jane@example.com", plan="starter")""",
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Customer's full name"},
            "email": {"type": "string", "description": "Customer's email address"},
            "plan": {
                "type": "string",
                "enum": ["starter", "professional", "enterprise"],
                "description": "Subscription plan"
            },
            "referral_code": {
                "type": "string",
                "description": "Optional referral code for tracking"
            }
        },
        "required": ["name", "email", "plan"]
    }
}
```

### Template 5: Diagnostic Tool

```python
diagnose_tool = {
    "name": "diagnose_issue",
    "description": """Run diagnostic checks on a customer's account or service.

Use this when: the customer is experiencing problems and you need to identify the cause.
Returns: a list of checks performed, their results, and recommended actions.

This tool is read-only and safe to run at any time.

Example: diagnose_issue(customer_id="cust_jane_smith", area="billing")""",
    "input_schema": {
        "type": "object",
        "properties": {
            "customer_id": {
                "type": "string",
                "description": "Customer ID (use search_customers to find it)"
            },
            "area": {
                "type": "string",
                "enum": ["billing", "access", "performance", "integration", "all"],
                "default": "all",
                "description": "Which area to diagnose"
            }
        },
        "required": ["customer_id"]
    }
}
```

---

## Common Anti-Patterns

### Anti-Pattern 1: CRUD Tools

```
BAD: create_user, read_user, update_user, delete_user, list_users,
     create_order, read_order, update_order, delete_order...

GOOD: onboard_customer, get_customer_overview, process_refund, search_orders
```

CRUD tools mirror your database, not your agent's tasks. Agents think in terms of workflows, not database operations.

### Anti-Pattern 2: Kitchen Sink Parameters

```
BAD: 15 required parameters, agent fills most incorrectly

GOOD: 2-3 required parameters, rest have sensible defaults
      Agent can always call with more specificity if needed
```

### Anti-Pattern 3: Opaque Return Values

```
BAD: Returns raw JSON with nested IDs, timestamps, internal flags
     {"usr": "a1b2", "ord": [{"oid": "x9", "st": 2, "ts": 1705344000}]}

GOOD: Returns human-readable, structured response
     {"user": "Jane Smith", "orders": [{"id": "order_laptop_jan15", "status": "shipped", "date": "2024-01-15"}]}
```

### Anti-Pattern 4: Silent Failures

```
BAD: Returns empty results with no explanation
     {"results": []}

GOOD: Returns empty results with context and suggestions
     {"results": [], "message": "No orders found for this customer in the last 30 days.",
      "suggestion": "Try expanding the date range or check the customer ID."}
```

### Anti-Pattern 5: Context Explosion

```
BAD: Tool returns full HTML page (50K+ tokens)
GOOD: Tool returns parsed, structured content (500 tokens)

BAD: Tool returns all 10,000 database records
GOOD: Tool returns top 10 with pagination metadata
```

---

## Tool Optimization Strategies

### Strategy 1: Tool Search Tool (Lazy Loading)

When you have 20+ tools, don't load them all. Give the agent a tool-search tool.

```python
tool_search = {
    "name": "find_tool",
    "description": "Search for available tools by keyword. Use this when you need a capability you don't currently have loaded.",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What you need to do"}
        },
        "required": ["query"]
    }
}

# Returns matching tool definitions on demand
# Reduces initial context from ~10K tokens to ~200 tokens
```

### Strategy 2: Programmatic Tool Calling

For predictable multi-step orchestration, call tools programmatically instead of through the LLM.

```python
# Instead of letting the agent call 3 tools sequentially (3 LLM rounds):
# 1. Agent calls get_user -> 2. Agent calls get_orders -> 3. Agent calls get_payment

# Do this (1 LLM round):
def get_user_context(user_id: str) -> dict:
    user = get_user(user_id)
    orders = get_orders(user_id, limit=5)
    payment = get_payment_status(user_id)
    return {"user": user, "orders": orders, "payment": payment}
```

### Strategy 3: Tool Use Examples

Add 1-5 examples to tool descriptions. This is the highest-impact optimization for tool accuracy.

```
"description": "Search for products...

Examples:
1. Find headphones under $50: search_products(query='headphones', max_price=50)
2. Browse new electronics: search_products(category='electronics', sort_by='newest')
3. Find a specific product: search_products(query='Sony WH-1000XM5')"
```
