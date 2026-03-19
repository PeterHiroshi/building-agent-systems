# Code Reviewer

**Pattern:** Evaluator-Optimizer
**Difficulty:** Intermediate
**What it does:** Reviews code iteratively, generating feedback and refining analysis until quality thresholds are met.

## Architecture

```
Code Input --> [Reviewer] --> Review Draft
                                 |
                            [Evaluator] --> Score + Feedback
                                 | score < threshold
                            [Reviewer] --> Revised Review (with feedback)
                                 | loop until satisfied
                            Final Review
```

## How to Run

```bash
pip install anthropic
export ANTHROPIC_API_KEY="your-key-here"
python agent.py
```

## Key Concepts Demonstrated

1. **Evaluator-Optimizer pattern** -- generator and evaluator as separate roles
2. **Iterative refinement** -- max 3 iterations with quality threshold
3. **Structured evaluation** -- JSON scores on specific dimensions
4. **Actionable feedback** -- evaluator tells generator exactly what to improve
