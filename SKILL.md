---
name: building-agent-systems
description: Use when designing or building AI agent systems, choosing between workflow patterns, diagnosing poor agent decisions, designing tools for agents, setting up evals, or managing context rot in long-running agents.
---

# Agent System Architect

## Overview

**Core principle:** Start with the simplest solution that meets the need. Complexity is a cost, not a feature.

Five disciplines compound each other: architecture selection → tool design → context engineering → think tool → evals. Get one wrong and the others can't compensate.

## Architecture Decision Tree

```
Is task complexity high + outcome unpredictable?
  YES → Parallel subtasks possible?
    YES → Multi-Agent (Orchestrator-Workers)
    NO  → Single Autonomous Agent
  NO  → Quality iteration needed?
    YES → Evaluator-Optimizer Workflow
    NO  → Multiple input types?
      YES → Router Workflow
      NO  → Sequential validation needed?
        YES → Prompt Chain
        NO  → Augmented LLM (single call)
```

**CRITICAL:** Prefer workflows over autonomous agents for well-defined tasks. Workflows = deterministic; agents = flexible but unpredictable.

See `references/patterns-reference.md` for full implementation of each pattern.

## Tool Design

Tools dominate agent context. Poor tools destroy good architectures.

**Five principles:** Merge granular APIs into agent-appropriate tools. Design for agent affordances. Return semantic IDs (`user_john_doe` not `u1234`). Errors must suggest correct next action. Pagination + filtering as defaults.

**Optimization:**

| Problem | Solution | Gain |
|---------|----------|------|
| Tool definitions > 10K tokens | Tool Search Tool (lazy-load) | 85% context reduction |
| Multi-step orchestration | Programmatic Tool Calling | 37% fewer tokens |
| Wrong tool usage | Tool Use Examples (1-5 per tool) | 72% → 90% accuracy |

**Tool dev cycle:** Prototype in Claude Code → write eval specs → feed failing transcripts back.

## Context Engineering

Context engineering = managing the full context window lifecycle, not just the initial prompt.

**Context rot:** Performance degrades as context fills. Quality > capacity even with 200K windows.

**System prompt:** "Right altitude" — specific enough to guide, flexible enough to adapt. Include role + decision criteria + tool guidance. Exclude what the model already knows.

**Long-running strategies:** Compaction (summarize + re-init at 70% full) → External memory (progress file) → Sub-agents (isolate polluting exploration) → Progressive disclosure (file-tree for > 20 tools) → Init pattern (init.sh + progress.txt + features.json for multi-day projects).

See `references/context-engineering-reference.md` for harness implementation.

## Think Tool

Add to any agent with > 3 sequential tool calls or policy-constrained decisions. Simple JSON tool with a single `thought` string parameter. +54% on complex policy tasks.

See `references/think-tool-reference.md` for JSON schema, system prompt instruction, and performance data.

## Multi-Agent Architecture

Use when: single agent fills context before completing, tasks parallelizable, specialist > generalist.

**Model selection:**

| Role | Model | Why |
|------|-------|-----|
| Orchestrator | Opus 4 | Full planning capacity |
| Workers | Sonnet 4 | Cost-efficient, sufficient |
| RAG context generation | Haiku | Fast, cheap, mechanical |

**Key orchestration rules:** Teach delegation explicitly in system prompt. Scale to complexity (1 subagent for simple, 10+ for complex). Parallel tool calling = 90% time reduction. Costs 15× more tokens than chat — budget accordingly.

## RAG for Knowledge-Heavy Agents

Naive RAG fails because chunks lose context. Use contextual retrieval: add 50-100 token context to each chunk before encoding, then hybrid (embeddings + BM25) + reranking. Reduces failure rate 67%.

See `references/rag-reference.md` for full pipeline and implementation.

## Evals

Build evals before building the agent (like TDD). No eval = no confidence.

**Three grader types:** Code-based (binary outcomes) + Model-based (quality/nuance) + Human (ground truth). Layer all three.

**Setup:** 20-50 real tasks (not synthetic) → unambiguous success criteria → 30/50/20 easy/medium/hard split → read transcripts, don't just check scores.

See `references/evals-reference.md` for agent-specific eval patterns and harness structure.

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Starting with autonomous agent | Use decision tree above first |
| Vague tool descriptions | Add examples + clear parameter docs |
| No think tool for complex agents | Add before shipping |
| Single agent for parallelizable work | Switch to Orchestrator-Workers |
| Evals built after agent | Build evals first |
| Ignoring context rot | Monitor perf vs. conversation length |

## Quick Start: 0→1 Agent

```
1. Define success criteria
2. Choose architecture (decision tree above)
3. Define tools needed
4. Write 20 eval cases first
5. Build tools (prototype → eval → iterate)
6. Add think tool if > 3 tool calls
7. Add multi-agent if single agent fills context
8. Sandbox file/network access
9. Ship to subset, iterate on regressions
```

## Superpowers Integration

- `superpowers:brainstorming` → clarify requirements before architecture decisions
- `superpowers:writing-plans` → turn architecture decisions into implementation tasks
- `superpowers:test-driven-development` → build evals first, agent second
- `superpowers:dispatching-parallel-agents` → implement multi-agent modules in parallel
- `superpowers:systematic-debugging` → diagnose agent failures with transcript analysis
