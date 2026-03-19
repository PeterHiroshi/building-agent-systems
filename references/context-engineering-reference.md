# Context Engineering Reference

## What Is Context Engineering?

Context engineering is managing the full lifecycle of everything that goes into your LLM's context window — not just the initial prompt, but system instructions, tool definitions, retrieved data, conversation history, and the user's current message. It's the discipline of making sure the right information is available at the right time, in the right format, at the right priority.

## The Context Stack

Every agent context window contains these layers, in order of prominence:

```
+-------------------------------------------+
|  SYSTEM PROMPT                            |  <- Most impactful, always present
|  (Role, domain, tools guidance, rules)    |
+-------------------------------------------+
|  TOOL DEFINITIONS                         |  <- Second most impactful
|  (Names, descriptions, schemas)           |
+-------------------------------------------+
|  RETRIEVED CONTEXT                        |  <- Injected just-in-time
|  (RAG results, memory, documents)         |
+-------------------------------------------+
|  CONVERSATION HISTORY                     |  <- Grows over time (context rot risk)
|  (Messages, tool calls, tool results)     |
+-------------------------------------------+
|  CURRENT TASK                             |  <- User's immediate request
+-------------------------------------------+
```

**Key insight:** Each layer has a different half-life and impact on agent behavior. System prompt stays forever; conversation history grows and degrades. Optimize from top to bottom.

## System Prompt Best Practices

### The Right Altitude Principle

Your system prompt should be specific enough to guide behavior but flexible enough to handle variation.

```
Too high (useless):
  "You are a helpful assistant."
  Problem: Agent has no domain knowledge, makes generic decisions

Too low (brittle):
  "When user asks about invoice, query table `invoices` with
   SQL: SELECT * FROM invoices WHERE user_id = {user_id}"
  Problem: Breaks on any variation, agent can't adapt

Right altitude:
  "You are a billing specialist. When users ask about invoices,
   retrieve the relevant invoice data and explain charges clearly.
   For date-range queries, default to last 30 days unless specified.
   Always confirm the amount before processing refunds."
  Why: Guides decisions without hardcoding implementation
```

### System Prompt Structure Template

```markdown
## Role
[Who you are, your expertise, your purpose]

## Domain Knowledge
[Critical facts the model needs — things it wouldn't know from training]

## Decision Criteria
[When to use which approach; how to prioritize competing goals]

## Tool Usage Guidance
[Which tools to use in which situations; sequencing hints]

## Output Format
[Structure, length, formatting expectations]

## Constraints
[What NOT to do; safety boundaries; limits]
```

### Token Budget Guidance

| Agent Type | System Prompt Budget | Why |
|------------|:-------------------:|-----|
| Simple chatbot | 500-1,000 tokens | Minimal guidance needed |
| Tool-using agent | 1,000-3,000 tokens | Tool usage patterns + domain rules |
| Complex multi-tool agent | 2,000-5,000 tokens | Detailed decision criteria + tool sequencing |
| Multi-agent orchestrator | 3,000-5,000 tokens | Delegation strategy + synthesis rules |

**If you need more than 5,000 tokens:** Consider sub-agents, progressive disclosure, or skills files loaded on demand.

## Managing Context Rot

### What Is Context Rot?

As conversation history grows, the agent's performance degrades. Not because the context window is full, but because:
- Recent information gets diluted by older, irrelevant messages
- Contradictory information from different turns confuses the model
- Tool call results accumulate and push important context further back
- The agent's "attention" spreads thinner across more content

### Symptoms

| Symptom | What's Happening | Severity |
|---------|-----------------|:--------:|
| Agent ignores recent instructions | Older context drowning out new info | High |
| Inconsistent behavior across turns | Contradictory info in history | Medium |
| Agent "forgets" established facts | Key info pushed too far back | High |
| Performance drops after 20+ turns | Context overload | Medium |
| Agent re-asks clarifying questions | Lost track of prior answers | Low |

### Strategy 1: Compaction (Re-initialization)

When context approaches capacity, summarize the conversation and start a new session with the summary injected.

```python
def should_compact(conversation, threshold=0.7):
    """Check if conversation is approaching context limits."""
    estimated_tokens = count_tokens(conversation)
    max_tokens = 200000  # Model's context window
    return estimated_tokens / max_tokens > threshold

def compact_conversation(conversation, system_prompt):
    """Summarize and re-initialize."""
    summary = client.messages.create(
        model="claude-haiku-4-5-20251001",  # Cheap for summarization
        max_tokens=2048,
        messages=[{
            "role": "user",
            "content": f"""Summarize this conversation, preserving:
1. All decisions made and their reasoning
2. Current task state and progress
3. Key facts established (user preferences, constraints)
4. Any unresolved questions or next steps

Conversation:
{format_conversation(conversation)}"""
        }]
    )

    # Start fresh with summary as context
    return {
        "system": system_prompt,
        "injected_context": f"## Previous Session Summary\n{summary.content[0].text}",
        "messages": []  # Fresh conversation
    }
```

**When to compact:**
- Context > 70% full
- Performance has noticeably degraded
- Agent starts repeating or contradicting itself

**What to preserve in compaction:**
- Decisions made and WHY
- Current task state
- User preferences and constraints
- Unresolved items

**What to drop:**
- Intermediate reasoning steps
- Failed tool calls and retries
- Exploratory conversation that led nowhere

### Strategy 2: External Memory (Structured Notes)

Give the agent tools to read and write persistent memory outside the context window.

```python
memory_write_tool = {
    "name": "write_memory",
    "description": "Save important information for later reference. Use this when you learn something that should persist across the conversation (user preferences, key decisions, task progress).",
    "input_schema": {
        "type": "object",
        "properties": {
            "key": {"type": "string", "description": "Category (e.g., 'user_preferences', 'project_status', 'decisions')"},
            "value": {"type": "string", "description": "The information to remember"}
        },
        "required": ["key", "value"]
    }
}

memory_read_tool = {
    "name": "read_memory",
    "description": "Retrieve previously saved information. Use this at the start of a new topic or when you need to recall earlier context.",
    "input_schema": {
        "type": "object",
        "properties": {
            "keys": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Categories to retrieve"
            }
        },
        "required": ["keys"]
    }
}
```

### Strategy 3: Sub-Agent Isolation

When a task would pollute the main agent's context (exploring files, research, large data analysis), delegate to a sub-agent with its own context window.

```python
# DON'T: Main agent reads 50 files (fills its context)
# DO: Sub-agent reads files, returns only the summary

async def isolated_research(task: str, tools: list) -> str:
    """Spawn a sub-agent with isolated context."""
    result = await client.messages.create(
        model="claude-sonnet-4-6-20250514",
        max_tokens=4096,
        system="You are a research assistant. Complete the task and return a concise summary of findings.",
        tools=tools,
        messages=[{"role": "user", "content": task}]
    )
    # Main agent receives only the summary, not all the intermediate work
    return extract_final_answer(result)
```

**When to use sub-agents:**
- File exploration (reading many files to find relevant ones)
- Web research (many searches, most results irrelevant)
- Data analysis (processing large datasets)
- Any task that generates lots of intermediate data

### Strategy 4: Progressive Context Disclosure

Don't load everything upfront. Give the agent tools to discover and load context as needed.

```python
# Instead of loading all 50 tool definitions at startup:
# Give 5 core tools + a discovery tool

tool_discovery = {
    "name": "list_available_tools",
    "description": "List available tool categories. Use when you need a capability not in your current tool set.",
    "input_schema": {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "description": "Filter by category (optional). Categories: search, data, communication, admin"
            }
        }
    }
}

# Agent discovers tools on demand:
# 1. "I need to send an email"
# 2. Calls list_available_tools(category="communication")
# 3. Gets back: send_email, post_slack, create_ticket
# 4. Now knows exactly which tool to use
```

### Strategy 5: The Init Pattern (Multi-Session Projects)

For agents that work across multiple sessions (days/weeks), use persistent files as external memory.

```
project/
  init.sh              # Reproducible environment setup
  claude-progress.txt  # What happened in previous sessions
  features.json        # Task list with status: failing/passing
  tests/               # Read-only test suite (agent can't delete)
```

**System prompt addition:**
```
At the start of each session:
1. Read claude-progress.txt to restore context from previous sessions
2. Read features.json to see current task list and priorities
3. Run tests on in-progress features to verify current state
4. Continue from where you left off
5. Update claude-progress.txt before ending each session
```

## Good vs Bad Context Engineering

### Example 1: Tool Definitions

```
BAD: 50 tool definitions loaded at startup (10K+ tokens)
     Agent confused about which tool to use
     Wrong tool selection 30% of the time

GOOD: 5 core tools + tool_search (200 tokens total)
      Agent finds the right tool on demand
      Wrong tool selection drops to 8%
```

### Example 2: Retrieved Context

```
BAD: Dump entire document (5K tokens) into context
     "Here's the full user manual, answer the question"
     Agent extracts the relevant paragraph itself (wasteful)

GOOD: Retrieve only relevant chunks (500 tokens)
      "Here are the 3 most relevant sections:"
      Agent focuses on what matters
```

### Example 3: Conversation History

```
BAD: Let history grow to 100K tokens over 50 turns
     Agent forgets early decisions
     Performance visibly degrades

GOOD: Compact at 70% capacity
      Key decisions preserved in summary
      Performance stays consistent
```

### Example 4: Error Context

```
BAD: Full stack trace + raw error object in context (2K tokens)
     Agent overwhelmed by irrelevant details

GOOD: Parsed error with actionable summary (100 tokens)
      "ConnectionError: Database 'users_db' unreachable.
       Last successful query: 2 minutes ago.
       Suggestion: Check if the database service is running."
```

## Dynamic Context Windowing

For agents that handle variable-complexity tasks, adjust context allocation dynamically.

```python
def allocate_context(task_complexity: str, total_budget: int = 200000) -> dict:
    """Allocate context budget based on task complexity."""
    allocations = {
        "simple": {
            "system_prompt": 1000,
            "tools": 2000,
            "retrieved_context": 5000,
            "conversation_history": 10000,
            "working_space": total_budget - 18000
        },
        "medium": {
            "system_prompt": 3000,
            "tools": 5000,
            "retrieved_context": 20000,
            "conversation_history": 30000,
            "working_space": total_budget - 58000
        },
        "complex": {
            "system_prompt": 5000,
            "tools": 3000,  # Use tool search, fewer loaded
            "retrieved_context": 50000,
            "conversation_history": 50000,
            "working_space": total_budget - 108000
        }
    }
    return allocations.get(task_complexity, allocations["medium"])
```

**Key insight:** Simple tasks need less context but more working space. Complex tasks need more retrieved context but can use tool search to keep tool definitions small.

## Context Engineering Checklist

```
System Prompt:
[ ] Right altitude (not too vague, not too rigid)
[ ] Includes role, decision criteria, tool guidance, constraints
[ ] Under 5K tokens (use sub-agents or skills if more needed)

Tool Definitions:
[ ] Each tool has "when to use" description
[ ] < 20 tools loaded at once (use tool search for more)
[ ] Examples included for complex tools

Retrieved Context:
[ ] Only relevant chunks injected (not full documents)
[ ] Context freshness tracked (stale data flagged)
[ ] Source attribution preserved

Conversation History:
[ ] Compaction strategy defined (when and how)
[ ] Key decisions preserved during compaction
[ ] Sub-agents used for context-heavy exploration

Overall:
[ ] Total context usage monitored
[ ] Performance tracked vs. conversation length
[ ] External memory for cross-session persistence
```
