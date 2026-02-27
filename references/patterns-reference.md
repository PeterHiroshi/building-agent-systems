# Agent Workflow Patterns Reference

## Pattern 1: Prompt Chaining

**Use when:** Task has clear sequential steps where each step validates/transforms the previous.

```
Input → [Step A] → Gate check → [Step B] → Gate check → [Step C] → Output
                       ↓ fail                  ↓ fail
                    Return error            Return error
```

**Implementation:**
```python
def prompt_chain(input_data):
    # Step 1: Extract
    result1 = claude.complete(f"Extract key entities from: {input_data}")
    if not validate_entities(result1):
        return {"error": "Extraction failed", "step": 1}

    # Step 2: Transform (gate passed)
    result2 = claude.complete(f"Analyze entities: {result1}")
    if not validate_analysis(result2):
        return {"error": "Analysis failed", "step": 2}

    # Step 3: Generate (gate passed)
    return claude.complete(f"Generate report from: {result2}")
```

**Best for:** Document processing pipelines, multi-step code generation, validation workflows.

---

## Pattern 2: Routing

**Use when:** Different input types need different handlers; classification improves quality.

```
Input → [Classifier] → route A → [Handler A] → Output
                     → route B → [Handler B] → Output
                     → route C → [Handler C] → Output
```

**Implementation:**
```python
def router(user_request):
    route = claude.complete(
        f"Classify this request as one of: [billing, technical, general]\n{user_request}",
        response_format={"type": "json", "schema": {"route": "string"}}
    )

    handlers = {
        "billing": billing_agent,
        "technical": technical_agent,
        "general": general_agent
    }
    return handlers[route["route"]](user_request)
```

**Best for:** Customer support, multi-domain assistants, specialized expert routing.

---

## Pattern 3: Parallelization

### Variant A: Sectioning (independent chunks)

```
Input → Split → [Worker 1] ↘
               [Worker 2] → Aggregate → Output
               [Worker 3] ↗
```

```python
import asyncio

async def parallel_process(document):
    sections = split_into_sections(document)
    results = await asyncio.gather(*[
        claude.complete_async(f"Analyze section: {s}")
        for s in sections
    ])
    return synthesize(results)
```

### Variant B: Voting (reliability)

```
Input → [Model 1] ↘
       [Model 2] → Vote → Consensus Output
       [Model 3] ↗
```

**Use voting for:** High-stakes decisions, factual verification, content safety checks.

---

## Pattern 4: Orchestrator-Workers

**Use when:** Task requires dynamic decomposition; number of subtasks unknown upfront.

```
Task → [Orchestrator]
           ↓ plan
       [Workers pool]
       W1 W2 W3 ... Wn  (spawned dynamically)
           ↓ results
       [Orchestrator] → Synthesis → Output
```

**Orchestrator system prompt skeleton:**
```
You are a research orchestrator. When given a task:
1. Analyze complexity: how many parallel workstreams are needed?
2. For simple tasks (1-3 aspects): use 1-3 workers
3. For complex tasks (many dimensions): use 5-10 workers
4. Each worker instruction must be:
   - Self-contained (no assumed shared context)
   - Specific about what to return
   - Bounded in scope (1-2 hour equivalent work)
5. After receiving all results, synthesize into coherent output

Always delegate research to workers. Never do research yourself.
```

**Worker system prompt:**
```
You are a specialist researcher. You will receive a specific research task.
Complete ONLY the assigned task. Return structured JSON with:
- findings: list of key findings
- confidence: high/medium/low
- sources: list of sources used
- gaps: what you couldn't find
```

---

## Pattern 5: Evaluator-Optimizer

**Use when:** Quality is subjective; "good enough" varies; iterative refinement needed.

```
Task → [Generator] → Draft
                        ↓
                   [Evaluator] → Score + Feedback
                        ↓ not good enough
                   [Generator] → Revised Draft
                        ↓ loop until satisfied
                   Final Output
```

```python
def evaluator_optimizer(task, max_iterations=3):
    draft = generate(task)

    for i in range(max_iterations):
        eval_result = claude.complete(f"""
        Evaluate this output for:
        1. Completeness (0-10)
        2. Accuracy (0-10)
        3. Clarity (0-10)

        Output: {draft}

        If average score < 8, provide specific improvement instructions.
        Return JSON: {{score: float, feedback: string, needs_revision: bool}}
        """)

        if not eval_result["needs_revision"] or i == max_iterations - 1:
            return draft

        draft = generate(task, context=f"Previous draft: {draft}\nFeedback: {eval_result['feedback']}")

    return draft
```

---

## Pattern 6: Initializer + Long-Running Agent (Harness Pattern)

**Use when:** Multi-day projects; agent needs persistent state across sessions.

```
File structure:
project/
  init.sh              # Reproducible environment setup
  claude-progress.txt  # Cross-session memory
  features.json        # Task list: [{name, status: "failing"|"passing", notes}]
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
5. Update claude-progress.txt with what you accomplished each session
6. Never modify or delete files in /tests directory
```
