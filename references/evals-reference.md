# Evals Reference

## Why Evals Come First

Build evals before building the agent. This is TDD for agent systems.

Without evals:
- You don't know if your agent works
- You can't measure the impact of changes
- You ship regressions without knowing
- "It seems to work" is your only quality signal

With evals:
- You define "done" before you start
- Every change is measured against a baseline
- Regressions are caught before shipping
- Quality improves systematically

## Three Grader Types

| Type | When to Use | Strength | Limitation | Cost |
|------|------------|----------|------------|:----:|
| **Code-based** | Binary outcomes, format checks, unit tests | Fast, deterministic, cheap | Can't judge nuance or quality | $ |
| **Model-based** | Quality assessment, rubric scoring, nuance | Handles subjective criteria | Slower, costs money, can be inconsistent | $$ |
| **Human** | Ground truth, edge cases, safety review | Catches blind spots | Expensive, slow, doesn't scale | $$$ |

**Always layer all three.** Code-based catches regressions cheaply. Model-based catches quality issues. Human catches what both miss.

## Setup Protocol

### Step 1: Collect Real Tasks (20-50)

```python
# Start with REAL examples from your domain, not synthetic ones
eval_tasks = [
    {
        "id": "task_001",
        "input": "I bought a laptop 3 weeks ago and the screen is flickering. I want a refund.",
        "expected_behavior": "Agent should check return policy (30 days), verify order, process refund",
        "difficulty": "easy",
        "tags": ["refund", "defective"]
    },
    {
        "id": "task_002",
        "input": "I received someone else's order but I also didn't get my own order.",
        "expected_behavior": "Agent should handle both issues: wrong item received + missing order",
        "difficulty": "hard",
        "tags": ["wrong_item", "missing_order", "multi_issue"]
    },
    # ... 18-48 more real tasks
]
```

**Why real tasks, not synthetic?** Synthetic tasks test what you think will happen. Real tasks test what actually happens. The edge cases in real tasks are the ones your agent will actually encounter.

### Step 2: Define Unambiguous Success Criteria

```python
# BAD: vague criteria
{"success": "Agent handles the request well"}

# GOOD: specific, measurable criteria
{
    "success_criteria": {
        "must": [
            "Correctly identifies this as a refund request",
            "Checks order date against 30-day policy",
            "Calls process_refund with correct order_id and amount"
        ],
        "must_not": [
            "Process refund without verifying order date",
            "Offer store credit without asking customer preference",
            "Skip identity verification"
        ],
        "bonus": [
            "Acknowledges customer frustration empathetically",
            "Proactively offers expedited replacement"
        ]
    }
}
```

### Step 3: Build a Balanced Set

```
Distribution:
  30% Easy   — straightforward, single-issue tasks
  50% Medium — typical complexity, may need 2-3 tools
  20% Hard   — edge cases, multi-issue, ambiguous inputs

Why this split?
  - Easy tasks catch catastrophic regressions
  - Medium tasks are your bread and butter
  - Hard tasks differentiate good from great
```

## Eval Harness Structure

```
Task Definition (input + success criteria)
    |
    v
Agent Execution (isolated environment)
    |
    v
Transcript Capture (full tool call history)
    |
    v
Multi-Grader Scoring
    |
    v
Score Aggregation + Regression Detection
    |
    v
Report Generation
```

### Minimal Eval Harness (Python)

```python
import json
import time
from dataclasses import dataclass

@dataclass
class EvalResult:
    task_id: str
    passed: bool
    scores: dict
    transcript: list
    duration_ms: int
    grader_details: dict

def run_eval_suite(tasks: list, agent_fn, graders: list) -> list[EvalResult]:
    """Run a full eval suite and return results."""
    results = []

    for task in tasks:
        # Execute agent in isolation
        start = time.time()
        transcript = run_agent_isolated(agent_fn, task["input"])
        duration_ms = int((time.time() - start) * 1000)

        # Run all graders
        scores = {}
        grader_details = {}
        for grader in graders:
            grader_result = grader(task, transcript)
            scores[grader.name] = grader_result["score"]
            grader_details[grader.name] = grader_result

        # Aggregate
        passed = all(s >= grader.threshold for s, grader in zip(scores.values(), graders))

        results.append(EvalResult(
            task_id=task["id"],
            passed=passed,
            scores=scores,
            transcript=transcript,
            duration_ms=duration_ms,
            grader_details=grader_details
        ))

    return results

def run_agent_isolated(agent_fn, input_text: str) -> list:
    """Run agent in isolated environment, capture full transcript."""
    # Use sandbox: no real API calls, no database writes
    # Return full tool call history for grading
    transcript = []

    def tool_interceptor(tool_name, tool_input):
        """Capture tool calls for the transcript."""
        result = mock_tool(tool_name, tool_input)
        transcript.append({
            "tool": tool_name,
            "input": tool_input,
            "output": result,
            "timestamp": time.time()
        })
        return result

    agent_fn(input_text, tool_executor=tool_interceptor)
    return transcript
```

### Code-Based Grader

```python
class CodeGrader:
    name = "code"
    threshold = 1.0  # Binary: pass or fail

    def __call__(self, task: dict, transcript: list) -> dict:
        checks = {}
        criteria = task.get("success_criteria", {})

        # Check "must" criteria
        for criterion in criteria.get("must", []):
            checks[criterion] = self.check_criterion(criterion, transcript)

        # Check "must_not" criteria
        for criterion in criteria.get("must_not", []):
            checks[f"NOT: {criterion}"] = not self.check_criterion(criterion, transcript)

        passed = all(checks.values())
        return {
            "score": 1.0 if passed else 0.0,
            "checks": checks,
            "reasoning": f"{'All' if passed else 'Not all'} required criteria met"
        }

    def check_criterion(self, criterion: str, transcript: list) -> bool:
        """Check a specific criterion against the transcript."""
        # Example: check if a specific tool was called
        if "calls process_refund" in criterion.lower():
            return any(t["tool"] == "process_refund" for t in transcript)
        if "checks order date" in criterion.lower():
            return any(t["tool"] == "get_order" for t in transcript)
        # Add more criterion checks as needed
        return False
```

### Model-Based Grader

```python
class ModelGrader:
    name = "model"
    threshold = 0.7  # 70% quality threshold

    def __call__(self, task: dict, transcript: list) -> dict:
        prompt = f"""You are evaluating an AI agent's handling of a customer request.

Task: {task['input']}
Expected behavior: {task.get('expected_behavior', 'Not specified')}

Agent transcript (tool calls and results):
{json.dumps(transcript, indent=2)}

Score the agent's performance on these dimensions (1-5 each):
1. Correctness: Did it achieve the right outcome?
2. Completeness: Did it address all aspects of the request?
3. Efficiency: Did it use tools effectively without unnecessary calls?
4. Policy compliance: Did it follow all stated rules?
5. Communication: Was its response clear and appropriate?

Return JSON:
{{"correctness": N, "completeness": N, "efficiency": N, "policy": N, "communication": N, "overall": N, "reasoning": "brief explanation"}}"""

        response = client.messages.create(
            model="claude-sonnet-4-6-20250514",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        result = json.loads(response.content[0].text)
        return {
            "score": result["overall"] / 5.0,
            "dimensions": result,
            "reasoning": result["reasoning"]
        }
```

### Human Grader (Spot Check)

```python
class HumanGrader:
    name = "human"
    threshold = 0.8

    def __call__(self, task: dict, transcript: list) -> dict:
        """Flag tasks for human review based on criteria."""
        needs_review = (
            task.get("difficulty") == "hard" or
            any(t["tool"] in ["process_refund", "delete_account"] for t in transcript) or
            len(transcript) > 10  # Complex interactions
        )

        if needs_review:
            return {
                "score": None,  # Pending human review
                "needs_review": True,
                "review_reason": "High-stakes or complex interaction",
                "review_url": generate_review_link(task["id"])
            }

        return {"score": 1.0, "needs_review": False}
```

## Agent-Specific Eval Patterns

### Coding Agent

```python
coding_eval = {
    "primary": {  # Code-based: does it work?
        "grader": "code",
        "checks": ["unit_tests_pass", "no_syntax_errors", "no_security_vulnerabilities"]
    },
    "secondary": {  # Model-based: is it good?
        "grader": "model",
        "rubric": "Code quality, readability, follows project conventions, no hardcoded values"
    },
    "metrics": ["test_pass_rate", "lines_changed", "time_to_complete"]
}
```

### Research Agent

```python
research_eval = {
    "primary": {  # Model-based: is it grounded?
        "grader": "model",
        "rubric": "All claims supported by cited sources, no hallucinated facts"
    },
    "secondary": {  # Model-based: is it complete?
        "grader": "model",
        "rubric": "Covers all major aspects of the topic, identifies key findings"
    },
    "tertiary": {  # Code-based: format check
        "grader": "code",
        "checks": ["has_sources", "has_summary", "word_count_in_range"]
    },
    "metrics": ["groundedness_score", "coverage_score", "source_count"]
}
```

### Customer Support Agent

```python
support_eval = {
    "primary": {  # Code-based: policy compliance
        "grader": "code",
        "checks": ["verified_identity", "checked_policy", "correct_resolution"]
    },
    "secondary": {  # Model-based: quality
        "grader": "model",
        "rubric": "Empathetic tone, clear explanation, resolved the issue"
    },
    "tertiary": {  # Human: spot check high-stakes
        "grader": "human",
        "trigger": "refund > $100 or account deletion"
    },
    "metrics": ["resolution_rate", "policy_compliance", "customer_satisfaction_proxy"]
}
```

## Regression Detection

### Tracking Scores Over Time

```python
def check_regression(current_scores: dict, baseline_scores: dict) -> dict:
    """Compare current eval scores against baseline."""
    regressions = {}

    for metric, current in current_scores.items():
        baseline = baseline_scores.get(metric, 0)
        delta = current - baseline
        pct_change = (delta / baseline * 100) if baseline > 0 else 0

        if pct_change < -5:
            regressions[metric] = {
                "severity": "warning" if pct_change > -10 else "critical",
                "baseline": baseline,
                "current": current,
                "delta": f"{pct_change:+.1f}%"
            }

    return regressions
```

### Release Gate Rules

```
WARNING (investigate before shipping):
  - Any metric drops > 5% from baseline
  - New failure on previously-passing easy task
  - Model-based grader flags a new category of issue

BLOCK (do not ship):
  - Any metric drops > 10% from baseline
  - Code-based grader failure rate increases
  - Hard task pass rate drops below 50%
  - Any safety-critical failure (wrong refund amount, data leak, etc.)
```

### Continuous Monitoring

```python
def eval_report(results: list[EvalResult], baseline: dict = None) -> str:
    """Generate a human-readable eval report."""
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    pass_rate = passed / total * 100

    by_difficulty = {}
    for r in results:
        diff = r.task_id.split("_")[0]  # Assuming task_id encodes difficulty
        by_difficulty.setdefault(diff, []).append(r.passed)

    report = f"""
## Eval Report
- Pass rate: {passed}/{total} ({pass_rate:.1f}%)
- Average duration: {sum(r.duration_ms for r in results) / total:.0f}ms

### By Difficulty
"""
    for diff, outcomes in by_difficulty.items():
        rate = sum(outcomes) / len(outcomes) * 100
        report += f"- {diff}: {rate:.1f}%\n"

    if baseline:
        regressions = check_regression(
            {"pass_rate": pass_rate},
            baseline
        )
        if regressions:
            report += "\n### REGRESSIONS DETECTED\n"
            for metric, info in regressions.items():
                report += f"- {metric}: {info['delta']} ({info['severity']})\n"

    # Flag failures for investigation
    failures = [r for r in results if not r.passed]
    if failures:
        report += f"\n### Failed Tasks ({len(failures)})\n"
        for f in failures[:10]:  # Show top 10
            report += f"- {f.task_id}: {f.grader_details}\n"

    return report
```

## Metrics Beyond Task Completion

Task completion rate is important but insufficient. Track these additional metrics:

| Metric | What It Measures | How to Compute |
|--------|-----------------|----------------|
| **Tool accuracy** | Agent selects the right tool | % of tool calls that are correct per transcript |
| **Tool efficiency** | Agent doesn't make unnecessary calls | Average tool calls per task vs. optimal |
| **Context usage** | How much context the agent consumes | Average tokens used per task |
| **Latency** | Time to complete tasks | p50, p90, p99 response times |
| **Cost per task** | Token cost per resolution | Input + output tokens per task |
| **Recovery rate** | Agent recovers from errors | % of error-then-success sequences |
| **Hallucination rate** | Agent makes unsupported claims | Model-graded groundedness |

## Eval Development Workflow

```
1. Start with 20 real tasks
2. Write code-based graders (binary pass/fail)
3. Run evals, read every failing transcript
4. Add model-based graders for quality dimensions
5. Run evals again, calibrate model grader thresholds
6. Ship agent, collect more real tasks from production
7. Grow eval set to 50-100 tasks over time
8. Add human review for edge cases
9. Set up regression detection on CI
10. Review and update eval set quarterly
```

## Common Mistakes

| Mistake | Why It's Bad | Fix |
|---------|-------------|-----|
| Synthetic-only eval tasks | Miss real-world edge cases | Start with real tasks, add synthetic to fill gaps |
| Only checking final output | Miss bad intermediate reasoning | Grade transcripts, not just final answers |
| Vague success criteria | Graders can't make consistent judgments | Make criteria specific and measurable |
| No baseline tracking | Can't detect regressions | Record scores for every eval run |
| Skipping transcript review | Scores hide real problems | Read 10 transcripts per eval run |
| Too few eval tasks | Results are noisy | 20 minimum, aim for 50+ |
