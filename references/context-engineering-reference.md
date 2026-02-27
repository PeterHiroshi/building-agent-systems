# Context Engineering Reference

## The Context Stack

Every agent context window contains these layers (in order of prominence):

```
┌─────────────────────────────────────────┐
│  SYSTEM PROMPT                          │  ← Most impactful, always present
│  (Role, domain, tools guidance, rules)  │
├─────────────────────────────────────────┤
│  TOOL DEFINITIONS                       │  ← Most visible, extremely impactful
│  (Names, descriptions, schemas)         │
├─────────────────────────────────────────┤
│  RETRIEVED CONTEXT                      │  ← Injected just-in-time
│  (RAG results, memory, notes)           │
├─────────────────────────────────────────┤
│  CONVERSATION HISTORY                   │  ← Grows over time (context rot risk)
│  (Messages, tool calls, results)        │
├─────────────────────────────────────────┤
│  CURRENT TASK                           │  ← User message
└─────────────────────────────────────────┘
```

## System Prompt Best Practices

### Right Altitude Principle

```
Too high (useless):          You are a helpful assistant.
Too low (rigid):             When user asks about invoice, query table
                             `invoices` with SQL: SELECT...
Right altitude:              You are a billing specialist. When users
                             ask about invoices, retrieve the relevant
                             invoice data and explain it clearly.
                             For date queries, default to last 30 days.
```

### System Prompt Structure Template

```markdown
## Role
[Who you are, your expertise, your purpose]

## Domain Knowledge
[Critical facts the model needs, not general knowledge]

## Decision Criteria
[When to use which approach; how to prioritize]

## Tool Usage Guidance
[Which tools to use in which situations; sequencing hints]

## Output Format
[Structure, length, formatting preferences]

## Constraints
[What NOT to do; limits; safety rules]
```

**Token budget guidance:**
- Simple chatbot: 500-1000 tokens
- Tool-using agent: 1000-3000 tokens
- Complex multi-tool agent: 2000-5000 tokens
- If you need more, consider sub-agents

## Managing Context Rot

### Symptoms of Context Rot

- Agent ignores recent instructions
- Inconsistent behavior across conversation
- Agent "forgets" established facts
- Performance degrades after 20+ turns

### Remediation Strategies

**1. Compaction (re-initialization)**
```python
# When context > 70% full:
summary = claude.complete(
    f"Summarize the key decisions, findings, and current state from this conversation. "
    f"Be comprehensive but concise.\n\n{conversation_history}"
)
new_session = start_new_session(
    system_prompt=original_system_prompt,
    injected_context=f"## Session Context (from previous session)\n{summary}"
)
```

**2. External Memory (structured notes)**
```
# Agent writes to memory file during session:
TOOL: write_memory
{
  "key": "user_preferences",
  "value": "User prefers bullet points, wants 3 options per recommendation"
}

# Agent reads at start of relevant contexts:
TOOL: read_memory
{"keys": ["user_preferences", "project_status"]}
```

**3. Sub-agent Isolation**

When a task would pollute the main agent's context (exploration, research, large file analysis):

```python
# DON'T: Let main agent read 50 files directly (fills context)
# DO: Spawn sub-agent with isolated context

result = spawn_subagent(
    task="Read all files in /src directory and identify components that handle authentication",
    tools=["read_file", "list_directory"],
    max_tokens=50000  # Sub-agent uses its own context budget
)
# Main agent receives only the summary
main_agent.inject(f"Authentication components found: {result}")
```

## RAG Context Enrichment

### The Contextual Retrieval Pipeline

```python
# Step 1: Chunk documents
chunks = split_document(doc, size=500, overlap=50)

# Step 2: Add context to each chunk (use Haiku for cost)
def enrich_chunk(chunk, doc_title, doc_summary):
    context = haiku.complete(f"""
    Document: {doc_title}
    Summary: {doc_summary}

    Chunk to contextualize:
    {chunk}

    Write 2-3 sentences explaining what this chunk is about
    and how it fits in the broader document. Be specific.
    """)
    return f"{context}\n\n{chunk}"

# Step 3: Build hybrid index
vector_index.add(enrich_chunk(chunk))  # For semantic search
bm25_index.add(enrich_chunk(chunk))    # For keyword search

# Step 4: Query with hybrid retrieval
def retrieve(query, top_k=20):
    vector_results = vector_index.search(query, k=top_k)
    bm25_results = bm25_index.search(query, k=top_k)
    combined = deduplicate_and_merge(vector_results, bm25_results)
    return reranker.rerank(combined, query, top_n=5)
```

**Cost optimization with prompt caching:**
```python
# System prompt with document corpus stays cached
cached_system = cache_control_prefix + "\n".join(
    f"Document {i}: {doc}" for i, doc in enumerate(document_corpus)
)
# Subsequent queries hit the cache: ~$1.02/M tokens vs $15/M tokens
```

## Progressive Context Disclosure

For large tool ecosystems (50+ tools), don't load all definitions upfront.

### File-Tree Tool Organization

```
mcp_servers/
  search/
    web_search.ts      # Search the internet
    arxiv_search.ts    # Search academic papers
  data/
    query_database.ts  # Query structured data
    read_csv.ts        # Read CSV files
  communication/
    send_email.ts      # Send emails
    post_slack.ts      # Post to Slack
```

**Discovery instruction in system prompt:**
```
Tool discovery: When you need to use a tool, first check if it exists:
1. Use `list_directory("mcp_servers")` to see available tool categories
2. Use `read_file("mcp_servers/<category>/<tool>.ts")` to read tool signature
3. Only then use the tool

Do NOT attempt to use tools you haven't discovered first.
```

## Agent Skills (Persistent Context)

For coding agents working on real projects, implement the Skills pattern:

```
project/
  .claude/
    skills/
      deploy-to-prod.md      # How to deploy (agent reads when deploying)
      run-tests.md           # Test commands and what failures mean
      database-schema.md     # DB structure the agent can't see directly
      code-conventions.md    # Project-specific patterns
```

**SKILL.md example:**
```markdown
---
name: run-tests
description: Use when running tests, debugging test failures, or verifying changes
---

# Running Tests

## Commands
- Unit tests: `npm test`
- Integration: `npm run test:integration`
- E2E: `npm run test:e2e` (requires server running)
- Coverage: `npm run test:coverage`

## Common Failures
- "Cannot find module" → Run `npm install` first
- "Port 3000 in use" → `lsof -ti:3000 | xargs kill`
- Timeout errors → Check if DB is running: `docker ps`

## Interpreting Results
- Jest output: look for "FAIL" lines, not just final count
- Integration failures often indicate environment issues, not code bugs
```
