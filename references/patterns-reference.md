# Agent Workflow Patterns Reference

## How to Use This Guide

Each pattern includes: when to use it, when NOT to use it, a real-world case study, implementation code, and common pitfalls. Start with the simplest pattern that fits your use case.

---

## Pattern 1: Augmented LLM (Single Call)

**Use when:** Task can be completed in a single LLM call with optional tool use.

```
Input -> [LLM + Tools] -> Output
```

This isn't really an "agent" — it's the baseline. But it's important to recognize when this is all you need, because every other pattern adds complexity on top.

**Implementation:**
```python
import anthropic

client = anthropic.Anthropic()

def augmented_llm(query: str, tools: list) -> str:
    response = client.messages.create(
        model="claude-sonnet-4-6-20250514",
        max_tokens=1024,
        tools=tools,
        messages=[{"role": "user", "content": query}]
    )
    # Handle tool use if needed
    if response.stop_reason == "tool_use":
        tool_result = execute_tool(response)
        return continue_with_result(response, tool_result)
    return response.content[0].text
```

**Real-world case study: FAQ Bot**
A SaaS company needed a bot to answer product questions. They started building a multi-agent system with routing. Then they realized: one LLM call with a retrieval tool answered 94% of questions correctly. The remaining 6% were escalated to humans. Total development time: 2 days vs. the estimated 3 weeks for the multi-agent approach.

**When NOT to use:** Task requires multiple sequential reasoning steps, quality iteration, or handling fundamentally different input types.

---

## Pattern 2: Prompt Chaining

**Use when:** Task has clear sequential steps where each step validates/transforms the previous output.

```
Input -> [Step A] -> Gate check -> [Step B] -> Gate check -> [Step C] -> Output
                        | fail                  | fail
                     Return error            Return error
```

The key feature is **gate checks** — validation between steps that catch failures early instead of letting them cascade.

**Implementation:**
```python
def prompt_chain(input_data: str) -> dict:
    # Step 1: Extract key entities
    result1 = client.messages.create(
        model="claude-sonnet-4-6-20250514",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": f"Extract key entities (people, organizations, dates, amounts) from this text. Return as JSON.\n\n{input_data}"
        }]
    )
    entities = parse_json(result1.content[0].text)

    # Gate: validate extraction
    if not entities or len(entities) < 1:
        return {"error": "No entities found", "step": 1}

    # Step 2: Analyze relationships
    result2 = client.messages.create(
        model="claude-sonnet-4-6-20250514",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": f"Analyze relationships between these entities. Identify key connections.\n\nEntities: {json.dumps(entities)}"
        }]
    )
    analysis = result2.content[0].text

    # Gate: validate analysis quality
    if len(analysis) < 50:
        return {"error": "Analysis too shallow", "step": 2}

    # Step 3: Generate report
    result3 = client.messages.create(
        model="claude-sonnet-4-6-20250514",
        max_tokens=2048,
        messages=[{
            "role": "user",
            "content": f"Write a structured report based on this analysis.\n\nEntities: {json.dumps(entities)}\nAnalysis: {analysis}"
        }]
    )

    return {"report": result3.content[0].text, "entities": entities}
```

**Real-world case study: Document Processing Pipeline**
A legal tech startup processes contracts: extract clauses -> classify risk level -> generate summary. Each step has clear success criteria (did we find clauses? is risk classification valid?). A prompt chain with 3 steps and 2 gates processes contracts in ~8 seconds with 91% accuracy. The gates catch extraction failures before they cause incorrect risk classifications downstream.

**When NOT to use:**
- Steps don't genuinely depend on each other (use parallel workers instead)
- You need more than 5-6 steps (break into sub-chains or use orchestrator)
- Step outcomes are highly variable (use evaluator-optimizer)

**Common pitfall:** Making the chain too long. Each step adds latency and token cost. If you have more than 5 steps, ask: can any be combined? Can any run in parallel?

---

## Pattern 3: Routing

**Use when:** Different input types need fundamentally different handling; classification improves quality over a one-size-fits-all approach.

```
Input -> [Classifier] -> route A -> [Handler A] -> Output
                      -> route B -> [Handler B] -> Output
                      -> route C -> [Handler C] -> Output
```

**Implementation:**
```python
def router(user_request: str) -> str:
    # Classify the request
    classification = client.messages.create(
        model="claude-haiku-4-5-20251001",  # Fast, cheap classification
        max_tokens=50,
        messages=[{
            "role": "user",
            "content": f"""Classify this customer request into exactly one category.
Categories: billing, technical, account, general

Request: {user_request}

Respond with just the category name."""
        }]
    )
    route = classification.content[0].text.strip().lower()

    # Route to specialized handler
    handlers = {
        "billing": handle_billing,    # Has access to billing tools + billing policies
        "technical": handle_technical, # Has access to docs search + error lookup
        "account": handle_account,     # Has access to account management tools
        "general": handle_general,     # General knowledge, no special tools
    }

    handler = handlers.get(route, handle_general)
    return handler(user_request)
```

**Real-world case study: Customer Support System**
An e-commerce company routed all support requests to a single agent with 20+ tools. The agent frequently used the wrong tools (billing tools for technical issues). Switching to a router with 4 specialized handlers — each with only its relevant tools — improved resolution accuracy from 64% to 87% and reduced average token usage by 40% (fewer wrong tool calls).

**When NOT to use:**
- Fewer than 3 distinct categories (handle with conditional logic in system prompt)
- Categories overlap significantly (agent will misroute)
- All routes need the same tools (routing adds overhead without benefit)

**Common pitfall:** Over-routing. If your router has 10+ categories, some probably overlap. Merge similar categories and let the handler deal with nuance.

---

## Pattern 4: Parallelization

### Variant A: Sectioning (independent chunks)

```
Input -> Split -> [Worker 1] \
               -> [Worker 2] -> Aggregate -> Output
               -> [Worker 3] /
```

```python
import asyncio

async def parallel_analyze(document: str) -> dict:
    sections = split_into_sections(document)

    # Run all analyses in parallel
    tasks = [
        analyze_section(section, i)
        for i, section in enumerate(sections)
    ]
    results = await asyncio.gather(*tasks)

    # Synthesize results
    synthesis = client.messages.create(
        model="claude-sonnet-4-6-20250514",
        max_tokens=2048,
        messages=[{
            "role": "user",
            "content": f"Synthesize these section analyses into a coherent summary:\n\n{json.dumps(results)}"
        }]
    )
    return {"sections": results, "synthesis": synthesis.content[0].text}
```

### Variant B: Voting (reliability)

```
Input -> [Model call 1] \
      -> [Model call 2] -> Vote -> Consensus Output
      -> [Model call 3] /
```

```python
async def vote_on_classification(input_text: str) -> str:
    # Run 3 independent classifications
    tasks = [classify(input_text) for _ in range(3)]
    votes = await asyncio.gather(*tasks)

    # Majority vote
    from collections import Counter
    vote_counts = Counter(votes)
    return vote_counts.most_common(1)[0][0]
```

**Real-world case study: Content Moderation**
A social platform needed high-accuracy content moderation. A single model call achieved 92% accuracy. Three parallel calls with majority voting achieved 97.5% — the disagreement cases were exactly the ambiguous content that needed human review. Cost increased 3x but false positives dropped 60%.

**When NOT to use voting:** When the task isn't classification or when speed matters more than accuracy.

**When NOT to use sectioning:** When sections depend on each other (use prompt chain instead).

---

## Pattern 5: Orchestrator-Workers

**Use when:** Task requires dynamic decomposition; number and type of subtasks unknown upfront.

```
Task -> [Orchestrator]
            | plan
        [Workers pool]
        W1 W2 W3 ... Wn  (spawned dynamically)
            | results
        [Orchestrator] -> Synthesis -> Output
```

**Orchestrator system prompt:**
```
You are a research orchestrator. When given a task:
1. Analyze complexity: how many parallel workstreams are needed?
2. For simple tasks (1-3 aspects): use 1-3 workers
3. For complex tasks (many dimensions): use 5-10 workers
4. Each worker instruction must be:
   - Self-contained (no assumed shared context)
   - Specific about what to return
   - Bounded in scope
5. After receiving all results, synthesize into coherent output

Always delegate research to workers. Never do research yourself.
If a worker fails, continue with the remaining results and note the gap.
```

**Worker system prompt:**
```
You are a specialist researcher. You will receive a specific research task.
Complete ONLY the assigned task. Return structured JSON with:
- findings: list of key findings with evidence
- confidence: high/medium/low
- sources: list of sources consulted
- gaps: what you couldn't find or verify
```

**Implementation:**
```python
async def orchestrator(task: str) -> dict:
    # Step 1: Plan the work
    plan = client.messages.create(
        model="claude-opus-4-6-20250514",  # Orchestrator needs planning capacity
        max_tokens=2048,
        messages=[{
            "role": "user",
            "content": f"Break this task into parallel research subtasks. Return JSON array of subtask descriptions.\n\nTask: {task}"
        }]
    )
    subtasks = parse_json(plan.content[0].text)

    # Step 2: Dispatch workers in parallel
    worker_tasks = [
        run_worker(subtask)
        for subtask in subtasks
    ]
    results = await asyncio.gather(*worker_tasks, return_exceptions=True)

    # Step 3: Filter failures, synthesize successes
    successes = [r for r in results if not isinstance(r, Exception)]
    failures = [str(r) for r in results if isinstance(r, Exception)]

    synthesis = client.messages.create(
        model="claude-opus-4-6-20250514",
        max_tokens=4096,
        messages=[{
            "role": "user",
            "content": f"Synthesize these research results into a comprehensive answer.\n\nResults: {json.dumps(successes)}\n\nNote: {len(failures)} workers failed. Gaps may exist."
        }]
    )

    return {
        "answer": synthesis.content[0].text,
        "worker_count": len(subtasks),
        "failures": len(failures)
    }

async def run_worker(subtask: str) -> dict:
    response = client.messages.create(
        model="claude-sonnet-4-6-20250514",  # Workers: cost-efficient
        max_tokens=2048,
        messages=[{
            "role": "user",
            "content": f"Research this specific topic and return structured findings as JSON.\n\nTopic: {subtask}"
        }]
    )
    return parse_json(response.content[0].text)
```

**Real-world case study: Codebase Migration**
A team needed to migrate a 500-file Python 2 codebase to Python 3. An orchestrator analyzed the dependency graph, grouped files by module, and dispatched workers for each module in parallel. Workers reported back migration results with confidence levels. The orchestrator then handled cross-module dependency conflicts. Total time: 4 hours (vs. estimated 2 weeks manual). 94% of files migrated correctly on first pass.

**When NOT to use:**
- Task is predictable and routine (use prompt chain — cheaper and faster)
- Subtasks are truly sequential (orchestrator overhead isn't justified)
- You can enumerate all subtasks upfront (use parallel workers instead — simpler)

**Common pitfall:** Making worker instructions dependent on shared context. Each worker should be completely self-contained. If a worker needs to know what another worker found, that's a signal you need sequential processing for those tasks.

---

## Pattern 6: Evaluator-Optimizer

**Use when:** Quality is subjective, benefits from iteration, and you can define evaluation criteria.

```
Task -> [Generator] -> Draft
                         |
                    [Evaluator] -> Score + Feedback
                         | not good enough
                    [Generator] -> Revised Draft (with feedback)
                         | loop until satisfied or max iterations
                    Final Output
```

**Implementation:**
```python
def evaluator_optimizer(task: str, max_iterations: int = 3) -> dict:
    draft = generate_initial(task)

    for i in range(max_iterations):
        # Evaluate
        evaluation = client.messages.create(
            model="claude-sonnet-4-6-20250514",
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": f"""Evaluate this output against the task requirements.

Task: {task}
Output: {draft}

Score 1-10 on: completeness, accuracy, clarity.
If average < 8, provide specific, actionable improvement instructions.
Return JSON: {{"scores": {{"completeness": N, "accuracy": N, "clarity": N}}, "average": N, "feedback": "...", "needs_revision": bool}}"""
            }]
        )
        eval_result = parse_json(evaluation.content[0].text)

        if not eval_result["needs_revision"]:
            return {"output": draft, "iterations": i + 1, "final_score": eval_result["average"]}

        # Revise with feedback
        revision = client.messages.create(
            model="claude-sonnet-4-6-20250514",
            max_tokens=2048,
            messages=[{
                "role": "user",
                "content": f"""Revise this output based on the feedback.

Original task: {task}
Current draft: {draft}
Feedback: {eval_result['feedback']}

Produce an improved version that addresses all feedback points."""
            }]
        )
        draft = revision.content[0].text

    return {"output": draft, "iterations": max_iterations, "final_score": eval_result["average"]}
```

**Real-world case study: Automated Code Review**
A development team built an agent to review PRs. Version 1 (single pass) caught 60% of issues that human reviewers found. Version 2 (evaluator-optimizer with 2 iterations) caught 82%. The evaluator specifically checked: "Did you miss any security issues? Did you check for edge cases?" — targeted feedback that the generator then addressed in revision.

**When NOT to use:**
- Output quality is binary (pass/fail) — use code-based validation instead
- Each iteration is expensive and quality gains are marginal after iteration 1
- Task has a clear "correct answer" (use prompt chain with validation gates)

**Common pitfall:** The evaluator being too lenient (always says "looks good"). Make evaluation criteria explicit and specific. "Is the code correct?" is too vague. "Does the code handle null inputs, validate types, and use parameterized queries?" is specific enough to catch real issues.

---

## Pattern 7: Long-Running Agent with Persistent State

**Use when:** Multi-session projects where the agent needs to maintain state across restarts.

```
File structure:
project/
  init.sh              # Reproducible environment setup
  claude-progress.txt  # Cross-session memory
  features.json        # Task list with status tracking
  tests/               # Agent cannot delete these
```

**features.json format:**
```json
[
  {
    "name": "User authentication",
    "status": "failing",
    "acceptance_criteria": "User can login with email/password, session persists 30 days",
    "test_command": "npm test -- --testPathPattern=auth"
  },
  {
    "name": "Dashboard view",
    "status": "passing",
    "notes": "Completed 2024-01-15"
  }
]
```

**Session startup instructions (add to system prompt):**
```
At the start of each session:
1. Run `cat claude-progress.txt` to restore context
2. Run `cat features.json` to see current task list
3. Run test suite on "in-progress" features to verify current state
4. Continue from where you left off
5. Update claude-progress.txt with what you accomplished
6. Never modify or delete files in /tests directory
```

**Real-world case study: Multi-Day Feature Implementation**
A solo developer used this pattern to build a full authentication system over 5 sessions spanning 3 days. The agent maintained context through `claude-progress.txt`, picking up exactly where it left off each session. Without persistent state, each session would have required re-explaining the full project context — wasting ~2000 tokens and often losing nuanced decisions from previous sessions.

**When NOT to use:**
- Task completes in a single session
- No state needs to persist between runs

---

## Choosing Between Patterns: Quick Reference

```
"I need to process documents step by step"         -> Prompt Chain
"I need to handle different types of requests"      -> Router
"I need to analyze many things at once"             -> Parallel Workers
"I don't know how many subtasks I'll need"          -> Orchestrator-Workers
"I need to iteratively improve output quality"      -> Evaluator-Optimizer
"I need to handle open-ended, unpredictable tasks"  -> Autonomous Agent (last resort)
"I need to work across multiple sessions"           -> Long-Running Agent
"Actually, it's simpler than I thought"             -> Augmented LLM
```

## Anti-Pattern: Mock-Heavy Testing in Agent-Generated Code

### The Problem
When coding agents (Claude Code, Aider, etc.) are tasked with TDD, they naturally
gravitate toward mock-heavy unit tests — mocks are fast to write, easy to make pass,
and satisfy the "GREEN" requirement quickly. But mock tests create **false confidence**:

- 100% test pass rate, 0% real-world confidence
- Modules work in isolation but fail when integrated
- N features "complete" but system doesn't boot
- Refactoring debt accumulates silently (mocks don't catch interface changes)

### The Fix: Real-Dependency-First Testing

**Prompt agents to prioritize real dependencies over mocks.**

```
## Testing Rules
- Mock ONLY: external paid APIs (Stripe, etc.), time, randomness
- REAL dependencies for: DB, Redis, filesystem, HTTP, WebSocket, git
- Integration tests ≥30% of test suite (real DB, real services)
- E2E tests ≥1 per feature (start full server, simulate user flow)
- Verification: count mock usage vs real tests — reject if mock-heavy
```

### Why Agents Default to Mocks
1. **Speed** — mocks make tests pass instantly (no setup overhead)
2. **Isolation** — agents can't easily spin up infrastructure
3. **Path of least resistance** — prompt says "TDD" but doesn't specify testing depth
4. **No feedback loop** — agent doesn't see the integration failure that happens later

### How to Fix in Dispatch Prompts
1. **Explicit layer requirements** — "≥30% integration, ≥1 E2E per feature"
2. **Anti-mock rule** — list what CANNOT be mocked (DB, Redis, FS, etc.)
3. **Verification checkpoint** — agent must audit mock ratio before completion
4. **Block > fake** — "if you need credentials, mark BLOCKED; don't write fake mocks"
5. **Test infra in CLAUDE.md** — document how to start real test dependencies

### Key Insight
The testing strategy you inject into the prompt directly determines the reliability
of agent output. **"TDD mandatory" alone produces mock-heavy code. You must specify
the testing depth explicitly.**
