# Simple Chatbot

**Pattern:** Augmented LLM
**Difficulty:** Beginner
**What it does:** A customer support chatbot with 4 tools, demonstrating the simplest agent pattern.

## Architecture

```
User Message --> [Claude + Tools] --> Response
```

No loops, no orchestration. Just a model with access to tools. This is the foundation all other patterns build on. **Start here.**

## How to Run

```bash
pip install anthropic
export ANTHROPIC_API_KEY="your-key-here"
python agent.py
```

## Key Concepts Demonstrated

1. **Tool design** -- Each tool has a clear "when to use" description
2. **Error recovery** -- Tool errors suggest the correct next action
3. **Semantic returns** -- Tool results use descriptive fields, not opaque IDs
4. **Eval cases** -- 10 test cases with 30/50/20 easy/medium/hard split
