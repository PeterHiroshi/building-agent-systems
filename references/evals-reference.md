# Evals Reference

## Three Grader Types

| Type | When to Use | Limitation |
|------|------------|------------|
| **Code-based** | Binary outcomes, unit tests, regex match | Can't judge nuance |
| **Model-based** | Quality, nuance, rubric scoring | Slower, costs money |
| **Human** | High-stakes decisions, ground truth | Expensive, slow |

Always layer all three. Code-based catches regressions cheaply; model-based catches quality issues; human catches blind spots.

## Setup Protocol

1. **Start with 20-50 real tasks** — never synthetic for first eval set
2. **Write unambiguous specifications** — define "success" exactly before grading
3. **Build balanced set** — 30% easy / 50% medium / 20% hard
4. **Read transcripts regularly** — scores lie; transcripts reveal actual behavior
5. **Layer graders** — code + model + spot human review

## Harness Structure

```
Task definition (input + expected output criteria)
    ↓
Agent execution (isolated environment, no side effects)
    ↓
Transcript capture (full tool call history)
    ↓
Multi-grader scoring
    ↓
Score aggregation + regression detection
```

**Isolation is critical:** Agent must run in an environment where it can't affect production state. Use sandboxed Bash, mock APIs, or test databases.

## Agent-Specific Eval Patterns

**Coding agent:**
```
Primary:   Unit tests (code-based) — does the code work?
Secondary: LLM rubric — did it follow constraints? (no hardcoded values, etc.)
```

**Research agent:**
```
Primary:   Groundedness — are all claims supported by sources?
Secondary: Coverage — did it find the main points?
Tertiary:  Hallucination check — model-based cross-reference
```

**Customer support agent:**
```
Primary:   Policy compliance (code-based rule check)
Secondary: Resolution quality (model-based rubric)
Tertiary:  Tone and empathy (human spot check)
```

## Model-Based Grader Prompt Template

```
You are evaluating an AI agent's response.

Task: {task_description}
Agent response: {agent_response}
Expected criteria: {success_criteria}

Score 1-5 on each dimension:
- Correctness: Does it achieve the task goal?
- Completeness: Does it address all required aspects?
- Constraint adherence: Does it follow all specified constraints?

Return JSON: {{"correctness": N, "completeness": N, "constraints": N, "overall": N, "reasoning": "..."}}
```

## Regression Detection

Track scores over time. Set thresholds:
- Drop > 5% on any metric → investigate before shipping
- Drop > 10% → block release

Compare against baseline (last known good version) not just absolute score.
