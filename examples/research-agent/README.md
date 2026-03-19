# Research Agent

**Pattern:** Prompt Chain
**Difficulty:** Beginner
**What it does:** Takes a topic, researches it using web search, extracts key facts, and produces a structured summary.

## Architecture

```
Topic -> [Search] -> Gate: results found?
                        -> [Extract Facts] -> Gate: facts have evidence?
                                                -> [Synthesize Summary] -> Output
```

## How to Run

```bash
pip install anthropic
export ANTHROPIC_API_KEY="your-key-here"
python agent.py "What are the latest developments in quantum computing?"
```

## Key Concepts Demonstrated

1. **Prompt chaining** — three sequential steps with validation gates
2. **Tool design** — search tool with clear "when to use" description
3. **Gate checks** — validation between steps to catch failures early
4. **Structured output** — JSON response with summary, facts, and sources
