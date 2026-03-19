# Multi-Agent Researcher

**Pattern:** Orchestrator-Workers
**Difficulty:** Advanced
**What it does:** An orchestrator breaks a complex research question into parallel subtasks, dispatches worker agents, and synthesizes their findings.

## Architecture

```
Research Question -> [Orchestrator (Opus)]
                          | plan: N subtasks
                     [Workers (Sonnet)] x N  (parallel)
                          | results
                     [Orchestrator] -> Synthesis -> Final Report
```

## How to Run

```bash
pip install anthropic
export ANTHROPIC_API_KEY="your-key-here"
python agent.py "Compare the approaches to AI safety taken by the top 5 AI labs"
```

## Key Concepts Demonstrated

1. **Orchestrator-Workers pattern** — dynamic task decomposition and parallel execution
2. **Model selection** — Opus for planning, Sonnet for focused research
3. **Graceful degradation** — if a worker fails, orchestrator continues with remaining results
4. **Structured worker output** — JSON with findings, confidence, and gaps
5. **Synthesis vs concatenation** — orchestrator produces coherent output, not a dump
