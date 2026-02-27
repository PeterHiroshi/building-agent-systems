# building-agent-systems

A Claude skill for designing and building world-class AI agent systems — based on Anthropic's engineering best practices.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/PeterHiroshi/building-agent-systems/main/install.sh | sh
```

Works with **Claude Code**, **Cursor**, and any tool that loads skills from `~/.claude/skills/`.

## What This Skill Does

Activates automatically when you're working on:

- **Architecture decisions** — choosing between prompt chains, routers, orchestrators, evaluator-optimizers
- **Tool design** — 5 principles for agent-appropriate tools, optimization strategies (Tool Search, Programmatic Calling, Tool Use Examples)
- **Context engineering** — managing context rot, compaction, external memory, sub-agent isolation
- **Think tool** — when and how to add a think tool (+54% on complex policy tasks)
- **Multi-agent systems** — orchestrator-worker patterns, model selection, 8 orchestration principles
- **RAG** — contextual retrieval pipeline with 67% failure reduction vs naive RAG
- **Evals** — three grader types, harness structure, agent-specific eval patterns

## Usage

No manual invocation needed. The skill loads automatically based on context. You can also reference it explicitly:

```
Use building-agent-systems to help me design this agent.
```

## File Structure

```
SKILL.md                              # Core skill (always loaded)
references/
  patterns-reference.md               # Full workflow pattern implementations
  context-engineering-reference.md    # Harness patterns, context strategies
  think-tool-reference.md             # JSON schema, prompting, benchmarks
  evals-reference.md                  # Grader types, harness, eval patterns
  rag-reference.md                    # Contextual retrieval pipeline
```

## Manual Install

```bash
git clone https://github.com/PeterHiroshi/building-agent-systems ~/.claude/skills/building-agent-systems
```

## Update

Re-run the install command — it replaces the existing installation.

## Background

This skill is distilled from Anthropic's engineering blog posts on agent systems. See [anthropic-blog-study](https://github.com/PeterHiroshi/anthropic-blog-study) for the source research.

## License

MIT
