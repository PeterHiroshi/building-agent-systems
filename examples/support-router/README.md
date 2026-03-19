# Support Router

**Pattern:** Router
**Difficulty:** Beginner
**What it does:** Classifies customer support requests and routes them to specialized handlers, each with their own tools and system prompts.

## Architecture

```
Customer Request -> [Classifier (Haiku)] -> billing  -> [Billing Handler]  -> Response
                                         -> technical -> [Technical Handler] -> Response
                                         -> account   -> [Account Handler]   -> Response
                                         -> general   -> [General Handler]   -> Response
```

## How to Run

```bash
pip install anthropic
export ANTHROPIC_API_KEY="your-key-here"
python agent.py "I was charged twice for my subscription last month"
```

## Key Concepts Demonstrated

1. **Router pattern** — cheap classifier routes to specialized handlers
2. **Model selection** — Haiku for classification, Sonnet for handling
3. **Tool isolation** — each handler only gets its relevant tools
4. **Cost efficiency** — routing is cheap, specialists are effective
