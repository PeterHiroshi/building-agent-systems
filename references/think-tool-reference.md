# Think Tool Reference

## JSON Schema

```python
{
  "name": "think",
  "description": "Use to reason step-by-step before taking action. Especially useful for: (1) long tool call chains where order matters, (2) decisions requiring policy checking, (3) evaluating whether to use a tool at all. Thoughts are not sent to external systems.",
  "input_schema": {
    "type": "object",
    "properties": {
      "thought": {"type": "string", "description": "Your reasoning process"}
    },
    "required": ["thought"]
  }
}
```

## System Prompt Instruction

Add this to the system prompt:

```
Use the think tool before:
- Taking actions that affect irreversible state
- When uncertain which tool to use next
- Checking whether an action complies with the policies above
- Evaluating tradeoffs between multiple valid next steps
```

## Domain-Specific Prompting

For policy-heavy domains (customer support, financial, healthcare), add examples:

```
When a customer requests a refund:
1. Use think to check: does this qualify under our 30-day policy?
2. Use think to verify: has the item been shipped?
3. Only then call process_refund()
```

## Think Tool vs Extended Thinking

| Think Tool | Extended Thinking |
|------------|-------------------|
| During tool chains (mid-response) | Before first response |
| Policy checking between actions | Complex single-step reasoning |
| Sequential decisions with consequences | Math, logic, code analysis |
| Long agentic sessions (5+ tool calls) | One-shot completions |

## Performance Data

| Domain | Metric | Without | With | Delta |
|--------|--------|---------|------|-------|
| Airline τ-bench | Task completion | 0.370 | 0.570 | +54% |
| Retail τ-bench | Task completion | 77.0% | 81.2% | +4.2% |
| SWE-Bench | Score | — | 0.623 SOTA | +1.6% |

**Rule of thumb:** Add think tool if agent makes > 3 sequential tool calls or operates in a policy-constrained domain.
