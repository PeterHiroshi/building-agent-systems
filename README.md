# Building Agent Systems

**The definitive guide to designing, building, and evaluating AI agent systems.**

Built on Anthropic's engineering best practices. From zero to production-ready agents.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Claude Code](https://img.shields.io/badge/Claude_Code-skill-blueviolet)](https://docs.anthropic.com/en/docs/claude-code)

---

## Why This Exists

Most agent guides are either too theoretical ("here's a taxonomy of agent types") or too shallow ("just add tools to your LLM"). This skill bridges the gap with **practical, battle-tested patterns** from Anthropic's engineering team.

**What you'll learn:**
- How to pick the right architecture for your agent (and avoid over-engineering)
- How to design tools that agents actually use correctly
- How to manage context so your agent doesn't degrade over long sessions
- How to build evals before you build your agent
- How to add metacognition (the "think tool") for complex reasoning

## Quick Install

```bash
curl -fsSL https://raw.githubusercontent.com/PeterHiroshi/building-agent-systems/main/install.sh | sh
```

Works with **Claude Code**, **Cursor**, and any tool that loads skills from `~/.claude/skills/`.

## Getting Started: Your First Agent in 15 Minutes

If you've never built an agent before, start here. We'll build a simple research agent step by step.

### Step 1: Define What Success Looks Like

Before writing any code, answer these questions:

```
1. What task does this agent perform?    → "Summarize a web page and extract key facts"
2. What does a good output look like?    → "3-5 bullet points, each with a source quote"
3. What tools does it need?              → "fetch_url, extract_text"
4. How will you know it's working?       → "Matches human-written summaries on 10 test pages"
```

This is the most important step. Skip it and you'll build the wrong thing.

### Step 2: Pick Your Architecture

Use the decision tree. For our research agent, the task is straightforward and sequential:

```
Is task complexity high + outcome unpredictable?
  NO → Quality iteration needed?
    NO → Multiple input types?
      NO → Sequential validation needed?
        YES → Prompt Chain ← This one
```

A **prompt chain** is the simplest multi-step architecture. Each step feeds into the next, with validation gates between them.

### Step 3: Build the Tools

```python
import anthropic

client = anthropic.Anthropic()

# Define tools the agent can use
tools = [
    {
        "name": "fetch_url",
        "description": "Fetch the text content of a web page. Use this when you need to read a URL. Returns the page text with HTML stripped.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The full URL to fetch (must start with https://)"
                }
            },
            "required": ["url"]
        }
    }
]
```

Notice: the tool description tells the agent **when** to use it, not just what it does. This is the single most important thing in tool design.

### Step 4: Wire It Up

```python
def research_agent(url: str) -> dict:
    """A simple research agent that summarizes a web page."""

    # Step 1: Fetch and extract content
    content = fetch_url(url)
    if not content or len(content) < 100:
        return {"error": "Could not fetch meaningful content from URL"}

    # Step 2: Extract key facts (with validation gate)
    facts_response = client.messages.create(
        model="claude-sonnet-4-6-20250514",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": f"Extract 5-10 key facts from this text. For each fact, include a direct quote as evidence.\n\nText:\n{content[:10000]}"
        }]
    )
    facts = facts_response.content[0].text

    # Gate: verify we got structured facts
    if "quote" not in facts.lower():
        return {"error": "Fact extraction failed — no evidence quotes found"}

    # Step 3: Synthesize into summary
    summary_response = client.messages.create(
        model="claude-sonnet-4-6-20250514",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": f"Summarize these facts into 3-5 bullet points. Each bullet should be one clear sentence.\n\nFacts:\n{facts}"
        }]
    )

    return {
        "summary": summary_response.content[0].text,
        "facts": facts,
        "source": url
    }
```

### Step 5: Write Your First Eval

```python
# Don't skip this. Evals are how you know your agent actually works.
test_cases = [
    {
        "url": "https://example.com/article-1",
        "expected_bullets": 3,  # minimum
        "must_mention": ["key topic from article"]
    },
]

def eval_research_agent(test_case):
    result = research_agent(test_case["url"])

    checks = {
        "no_error": "error" not in result,
        "has_bullets": result.get("summary", "").count("- ") >= test_case["expected_bullets"],
        "mentions_key_topics": all(
            topic.lower() in result.get("summary", "").lower()
            for topic in test_case["must_mention"]
        ),
    }

    return {"passed": all(checks.values()), "checks": checks}
```

**Congratulations** — you've just built a research agent with a prompt chain architecture, proper tool design, validation gates, and an eval. This is the foundation everything else builds on.

## Architecture Decision Flowchart

```
                        START HERE
                            |
                  Is the task well-defined?
                   /                    \
                 YES                     NO
                  |                       |
        Multiple steps needed?    Need flexibility to
         /              \         handle unknowns?
       YES              NO         /           \
        |                |       YES            NO
  Steps independent?   Just an         |        Reconsider if
   /          \      Augmented     Parallel     you need an
  YES         NO       LLM      subtasks?       agent at all
   |           |    (single        /      \
Parallel    Sequential  call)    YES       NO
Workers     Prompt               |          |
            Chain            Orchestrator   Single
               |                Workers    Autonomous
         Need quality                       Agent
         iteration?
          /      \
        YES       NO
         |         |
    Evaluator    Router
    Optimizer   (if multiple
                 input types)
```

### When to Use Each Pattern

| Pattern | Best For | Avoid When | Complexity | Token Cost |
|---------|----------|------------|:----------:|:----------:|
| **Augmented LLM** | Single-step tasks, Q&A | Multi-step reasoning needed | Low | $ |
| **Prompt Chain** | Document processing, pipelines | Steps aren't truly sequential | Low | $$ |
| **Router** | Multi-domain support, triage | < 3 distinct categories | Low | $$ |
| **Parallel Workers** | Independent analysis tasks | Tasks depend on each other | Medium | $$ |
| **Orchestrator-Workers** | Complex research, code generation | Task is predictable/routine | High | $$$ |
| **Evaluator-Optimizer** | Writing, code review, creative | Binary pass/fail outcomes | Medium | $$$ |
| **Autonomous Agent** | Open-ended exploration | Well-defined workflows exist | Very High | $$$$ |

**The golden rule:** Start with the simplest pattern that could work. You can always add complexity later; removing it is much harder.

## What's Inside

### Core Skill
- **[SKILL.md](SKILL.md)** — The main skill file. Loaded automatically by Claude Code when you're working on agent systems.

### Reference Guides
Each reference goes deep on a specific topic:

| Reference | What You'll Learn |
|-----------|-------------------|
| **[Workflow Patterns](references/patterns-reference.md)** | 6 architecture patterns with code, diagrams, and real-world case studies |
| **[Tool Design](references/tool-design-reference.md)** | How to design tools agents use correctly — MVT, error recovery, 5 templates |
| **[Context Engineering](references/context-engineering-reference.md)** | Managing the context window lifecycle — rot, compaction, dynamic windowing |
| **[Think Tool](references/think-tool-reference.md)** | Adding metacognition to agents — implementations in Python, TypeScript, Go |
| **[Evals](references/evals-reference.md)** | Building evaluation frameworks — graders, harnesses, regression detection |
| **[RAG](references/rag-reference.md)** | Contextual retrieval pipeline — 67% failure reduction vs naive RAG |

### Examples
Complete, runnable agent implementations:

| Example | Pattern Used | Difficulty |
|---------|-------------|:----------:|
| **[Research Agent](examples/research-agent/)** | Prompt Chain | Beginner |
| **[Support Router](examples/support-router/)** | Router | Beginner |
| **[Code Review Agent](examples/code-review-agent/)** | Evaluator-Optimizer | Intermediate |
| **[Multi-Agent Researcher](examples/multi-agent-researcher/)** | Orchestrator-Workers | Advanced |

## Key Concepts at a Glance

### The Five Disciplines

Building great agent systems requires five disciplines that compound each other:

```
Architecture Selection
        |
        v
   Tool Design -----> If tools are bad, nothing else matters
        |
        v
Context Engineering -> Keeps the agent effective over time
        |
        v
   Think Tool -------> Prevents reasoning failures mid-chain
        |
        v
     Evals ----------> Proves it actually works
```

Get one wrong and the others can't compensate. Get them all right and they multiply each other's effectiveness.

### The #1 Mistake

> **Starting with an autonomous agent when a workflow would do.**

Autonomous agents are flexible but unpredictable. Workflows are deterministic and debuggable. Always ask: "Can I solve this with a prompt chain or router?" If yes, do that first.

## Manual Install

```bash
git clone https://github.com/PeterHiroshi/building-agent-systems ~/.claude/skills/building-agent-systems
```

## Update

Re-run the install command — it replaces the existing installation.

## Contributing

We welcome contributions. See **[CONTRIBUTING.md](CONTRIBUTING.md)** for guidelines.

Areas where help is especially welcome:
- Additional example implementations
- Translations
- Real-world case studies
- Eval scripts and benchmarks

## Background

This skill is distilled from Anthropic's engineering blog posts on agent systems. See [anthropic-blog-study](https://github.com/PeterHiroshi/anthropic-blog-study) for the source research.

## License

MIT
