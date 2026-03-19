---
name: building-agent-systems
description: Use when designing or building AI agent systems, choosing between workflow patterns, diagnosing poor agent decisions, designing tools for agents, setting up evals, or managing context rot in long-running agents.
---

# Agent System Architect

## Overview

**Core principle:** Start with the simplest solution that meets the need. Complexity is a cost, not a feature.

Five disciplines compound each other: architecture selection -> tool design -> context engineering -> think tool -> evals. Get one wrong and the others can't compensate.

## Architecture Decision Tree

```
Is task complexity high + outcome unpredictable?
  YES -> Parallel subtasks possible?
    YES -> Multi-Agent (Orchestrator-Workers)
    NO  -> Single Autonomous Agent (use sparingly)
  NO  -> Quality iteration needed?
    YES -> Clear evaluation criteria exist?
      YES -> Evaluator-Optimizer Workflow
      NO  -> Human-in-the-loop review instead
    NO  -> Multiple input types or domains?
      YES -> > 3 distinct categories?
        YES -> Router Workflow
        NO  -> Handle in system prompt with conditional logic
      NO  -> Sequential steps with validation?
        YES -> Steps > 5?
          YES -> Consider breaking into sub-chains
          NO  -> Prompt Chain
        NO  -> Single LLM call sufficient?
          YES -> Augmented LLM (single call)
          NO  -> Re-evaluate: you may be underestimating complexity
```

### Architecture Selection: Real-World Examples

| Use Case | Wrong Choice | Right Choice | Why |
|----------|-------------|--------------|-----|
| Email triage | Autonomous agent | Router | 3 categories (urgent/normal/spam), deterministic |
| Code migration | Prompt chain | Orchestrator-Workers | File count unknown upfront, parallelizable |
| Blog post writing | Single LLM call | Evaluator-Optimizer | Quality is subjective, benefits from iteration |
| Customer support | Complex router | Prompt chain + think tool | Sequential policy checks, not routing |
| Data pipeline QA | Autonomous agent | Prompt chain | Steps are fixed and well-defined |

### Performance Characteristics

| Pattern | Latency | Token Cost | Reliability | Debuggability |
|---------|:-------:|:----------:|:-----------:|:-------------:|
| Augmented LLM | Lowest | $ | Highest | Trivial |
| Prompt Chain | Low | $$ | High | Easy (step-by-step) |
| Router | Low | $$ | High | Easy (check classification) |
| Parallel Workers | Low (parallel) | $$ | High | Medium |
| Evaluator-Optimizer | Medium-High | $$$ | Medium | Medium (check feedback loops) |
| Orchestrator-Workers | High | $$$-$$$$ | Medium | Hard (distributed state) |
| Autonomous Agent | Unpredictable | $$$$ | Lowest | Hardest |

**CRITICAL:** Prefer workflows over autonomous agents for well-defined tasks. Workflows = deterministic and debuggable; agents = flexible but unpredictable.

See `references/patterns-reference.md` for full implementation of each pattern with case studies.

## Tool Design

Tools dominate agent context. Poor tools destroy good architectures.

### Five Design Principles

1. **Merge granular APIs** into agent-appropriate operations (e.g., `update_user_profile` not `PATCH /users/:id`)
2. **Design for agent affordances** — descriptions say WHEN to use the tool, not just what it does
3. **Return semantic IDs** — `user_john_doe` not `u1234` so the agent can reason about them
4. **Errors suggest next action** — "User not found. Try search_users to find the correct user ID." not just "404"
5. **Pagination + filtering as defaults** — agents handle 10 results well, 1000 results badly

### Minimal Viable Tool (MVT)

Build the smallest tool that lets the agent accomplish the task. Add complexity only when evals show the agent struggling.

```
MVT Checklist:
[ ] Tool does ONE thing well
[ ] Description explains WHEN to use it (not just what)
[ ] 1-3 required parameters, optional params have sensible defaults
[ ] Error messages include a suggested recovery action
[ ] Returns structured data the agent can reason about
[ ] Has 1-3 usage examples in the description
```

### Tool Optimization

| Problem | Solution | Gain |
|---------|----------|------|
| Tool definitions > 10K tokens | Tool Search Tool (lazy-load) | 85% context reduction |
| Multi-step orchestration | Programmatic Tool Calling | 37% fewer tokens |
| Wrong tool usage | Tool Use Examples (1-5 per tool) | 72% -> 90% accuracy |
| Ambiguous tool selection | Clearer `when to use` descriptions | Reduces mis-selection |

### Common Anti-Patterns

| Anti-Pattern | Problem | Fix |
|-------------|---------|-----|
| CRUD-style tools | Too granular, agent makes many calls | Merge into task-oriented tools |
| Opaque errors | Agent retries blindly | Return actionable error messages |
| Missing descriptions | Agent guesses when to use tool | Add `when to use` + examples |
| Too many required params | Agent fills incorrectly | Use sensible defaults |
| Returning raw HTML/XML | Wastes context tokens | Parse and return structured data |

See `references/tool-design-reference.md` for complete tool templates and error recovery patterns.

**Tool dev cycle:** Prototype in Claude Code -> write eval specs -> feed failing transcripts back -> iterate.

## Context Engineering

Context engineering = managing the full context window lifecycle, not just the initial prompt.

**Context rot:** Performance degrades as context fills. Quality > capacity even with 200K windows.

### The Context Stack

```
System Prompt        <- Most impactful, always present
Tool Definitions     <- Second most impactful, shapes behavior
Retrieved Context    <- Injected just-in-time (RAG, memory)
Conversation History <- Grows over time (context rot risk)
Current Task         <- User's immediate request
```

Each layer has a different half-life and impact on agent behavior. Optimize from top to bottom.

### System Prompt: The Right Altitude

```
Too high (useless):    "You are a helpful assistant."
Too low (brittle):     "When user says X, run SQL query: SELECT..."
Right altitude:        "You are a billing specialist. Retrieve invoice data
                        and explain it clearly. Default to last 30 days."
```

Include: role + decision criteria + tool guidance + constraints.
Exclude: what the model already knows, verbose examples for simple tasks.

### Long-Running Agent Strategies

1. **Compaction** — Summarize and re-initialize when context > 70% full
2. **External memory** — Write key decisions to a progress file the agent reads each session
3. **Sub-agents** — Isolate polluting exploration (research, file scanning) in sub-agents
4. **Progressive disclosure** — Lazy-load tools and context as needed, not all upfront
5. **Init pattern** — For multi-day projects: `init.sh` + `progress.txt` + `features.json`

### Good vs Bad Context Engineering

```
BAD:  Stuff the entire codebase into context "just in case"
GOOD: Give the agent a file-tree tool to explore what it needs

BAD:  Let conversation history grow without bounds
GOOD: Compact at 70% capacity, preserving key decisions

BAD:  Put all 50 tool definitions in the system prompt
GOOD: Give 5 core tools + a tool-search tool for the rest

BAD:  Repeat instructions at every turn
GOOD: Put stable instructions in system prompt, dynamic info in retrieved context
```

See `references/context-engineering-reference.md` for implementation patterns.

## Think Tool

Add to any agent with > 3 sequential tool calls or policy-constrained decisions. Simple JSON tool with a single `thought` string parameter. +54% on complex policy tasks (Airline tau-bench).

**When to add:**
- Agent makes > 3 sequential tool calls
- Policy-constrained decisions (refunds, access control, moderation)
- Multi-step plans where order matters
- Agent needs to evaluate tradeoffs before acting

**When NOT needed:**
- Simple single-tool-call agents
- Routing/classification tasks
- Tasks with no ambiguity in action sequence

See `references/think-tool-reference.md` for JSON schema, multi-language implementations, and performance data.

## Multi-Agent Architecture

Use when: single agent fills context before completing, tasks are parallelizable, specialist > generalist.

### Model Selection

| Role | Model | Why |
|------|-------|-----|
| Orchestrator | Claude Opus | Full planning capacity, complex delegation |
| Workers | Claude Sonnet | Cost-efficient, sufficient for focused tasks |
| RAG/context generation | Claude Haiku | Fast, cheap, mechanical tasks |

### Key Orchestration Rules

1. **Teach delegation explicitly** in system prompt ("delegate research to workers, never do it yourself")
2. **Scale to complexity** — 1 subagent for simple, 10+ for complex
3. **Make worker instructions self-contained** — no assumed shared context
4. **Parallel tool calling** = 90% time reduction vs sequential
5. **Budget accordingly** — costs 15x more tokens than single-agent chat
6. **Workers report structured results** — JSON with findings, confidence, gaps
7. **Orchestrator synthesizes** — never just concatenates worker outputs
8. **Fail gracefully** — if a worker fails, the orchestrator continues with remaining results

## RAG for Knowledge-Heavy Agents

Naive RAG fails because chunks lose context. Use contextual retrieval: add 50-100 token context to each chunk before encoding, then hybrid search (embeddings + BM25) + reranking. Reduces failure rate 67%.

See `references/rag-reference.md` for full pipeline and implementation.

## Evals

Build evals before building the agent (like TDD). No eval = no confidence.

### Three Grader Types

1. **Code-based** — Binary outcomes, unit tests, regex matching (cheap, fast)
2. **Model-based** — Quality, nuance, rubric scoring (slower, more capable)
3. **Human** — Ground truth, edge cases, blind spots (expensive, authoritative)

Layer all three. Code-based catches regressions; model-based catches quality drops; human catches blind spots.

### Quick Setup

```
1. Collect 20-50 real tasks (not synthetic)
2. Write unambiguous success criteria for each
3. Build balanced set: 30% easy / 50% medium / 20% hard
4. Implement code-based graders first
5. Add model-based graders for nuanced dimensions
6. Read transcripts regularly — scores lie, transcripts reveal truth
7. Track scores over time; block releases on > 5% regression
```

See `references/evals-reference.md` for agent-specific eval patterns, grader templates, and regression detection.

## Common Mistakes

| Mistake | Why It Happens | Fix |
|---------|---------------|-----|
| Starting with autonomous agent | Agents seem powerful | Use decision tree — workflows first |
| Vague tool descriptions | Copied from API docs | Rewrite: when to use + examples |
| No think tool for complex agents | Seems unnecessary | Add before shipping — +54% on policy tasks |
| Single agent for parallelizable work | Simpler to implement | Switch to Orchestrator-Workers |
| Evals built after agent | "We'll add tests later" | Build evals first (TDD for agents) |
| Ignoring context rot | Works fine in short tests | Monitor performance vs. conversation length |
| Too many tools loaded at once | "Agent might need them" | Tool Search Tool for lazy loading |
| Raw API responses as tool output | Quick to implement | Parse and return structured data |

## Quick Start: 0 -> 1 Agent

```
1. Define success criteria (what does "working" look like?)
2. Choose architecture (decision tree above — start simple)
3. Define tools needed (MVT — minimal viable tool)
4. Write 20 eval cases first (before building the agent)
5. Build tools (prototype -> eval -> iterate)
6. Add think tool if > 3 tool calls or policy decisions
7. Add multi-agent if single agent fills context
8. Sandbox file/network access
9. Ship to subset of users, iterate on regressions
```

## Debugging Agent Failures

When an agent fails, check these in order:

```
1. Tool problems?     -> Read the transcript: is the agent calling wrong tools?
                         Fix: Better tool descriptions, add examples
2. Context problems?  -> Is the agent ignoring recent information?
                         Fix: Compact context, add sub-agents for exploration
3. Reasoning problems? -> Is the agent making wrong decisions despite good info?
                         Fix: Add think tool, improve system prompt decision criteria
4. Architecture problems? -> Is the agent fundamentally unable to handle this task shape?
                            Fix: Switch pattern (see decision tree)
```

## Superpowers Integration

- `superpowers:brainstorming` -> clarify requirements before architecture decisions
- `superpowers:writing-plans` -> turn architecture decisions into implementation tasks
- `superpowers:test-driven-development` -> build evals first, agent second
- `superpowers:dispatching-parallel-agents` -> implement multi-agent modules in parallel
- `superpowers:systematic-debugging` -> diagnose agent failures with transcript analysis
