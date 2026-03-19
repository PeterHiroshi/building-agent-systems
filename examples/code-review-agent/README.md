# Code Review Agent

**Pattern:** Evaluator-Optimizer
**Difficulty:** Intermediate
**What it does:** Reviews code, provides feedback, and iteratively improves its review by checking for common gaps.

## Architecture

```
Code -> [Reviewer] -> Initial Review
                          |
                     [Evaluator] -> "Did you check security? Edge cases? Conventions?"
                          |
                     [Reviewer] -> Improved Review (addresses gaps)
                          |
                     Final Review
```

## How to Run

```bash
pip install anthropic
export ANTHROPIC_API_KEY="your-key-here"
python agent.py path/to/file.py
```

## Key Concepts Demonstrated

1. **Evaluator-Optimizer loop** — review improves through targeted feedback
2. **Think tool** — reviewer reasons about code before writing review
3. **Structured evaluation criteria** — evaluator checks specific dimensions
4. **Iteration capping** — max 2 iterations to control cost
