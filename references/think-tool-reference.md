# Think Tool Reference

## What Is a Think Tool?

A think tool is a simple tool with a single `thought` string parameter that lets an agent reason step-by-step during a tool-use chain. The model writes its reasoning into the `thought` parameter. The tool "executes" by doing nothing — it just returns the thought back. But the act of writing structured reasoning dramatically improves decision quality.

**Why it works:** During agentic loops, the model generates tool calls. Without a think tool, the model jumps straight from observation to action. The think tool creates a deliberate pause point where the model can evaluate what it's learned, check policies, and plan its next move.

## JSON Schema

```json
{
  "name": "think",
  "description": "Use this tool to reason step-by-step before taking action. Your thoughts are private and not sent to external systems. Use it when: (1) you need to plan a multi-step approach, (2) you need to check a policy or rule before acting, (3) you're choosing between multiple valid options, (4) the next action has irreversible consequences.",
  "input_schema": {
    "type": "object",
    "properties": {
      "thought": {
        "type": "string",
        "description": "Your step-by-step reasoning"
      }
    },
    "required": ["thought"]
  }
}
```

## When to Add a Think Tool

**Add it when:**
- Agent makes > 3 sequential tool calls
- Policy-constrained decisions (refunds, access control, content moderation)
- Multi-step plans where ordering matters
- Agent needs to evaluate tradeoffs before acting
- High-stakes actions with irreversible consequences

**Skip it when:**
- Simple single-tool-call agents
- Routing/classification tasks (no sequential reasoning needed)
- Tasks with unambiguous action sequences
- Speed is critical and reasoning overhead isn't justified

## System Prompt Instruction

Add this to any agent's system prompt when you include the think tool:

```
Before taking actions, use the think tool to:
- Plan your approach for multi-step tasks
- Check whether an action complies with the policies above
- Evaluate tradeoffs when multiple approaches are valid
- Verify you have all required information before proceeding
- Assess whether an action is reversible

Your thoughts are private and not visible to the user or external systems.
```

## Domain-Specific Prompting

For different domains, the think tool prompt should emphasize different reasoning patterns.

### Customer Support

```
When handling customer requests, use the think tool to:
1. Verify: Does this request fall within our 30-day return policy?
2. Check: Has the order been shipped? Is it a final-sale item?
3. Validate: Do I have the order ID and customer verification?
4. Decide: Full refund, partial refund, or store credit?

Only call process_refund() after thinking through all of the above.
```

### Code Generation

```
When writing or modifying code, use the think tool to:
1. Understand the existing code structure before making changes
2. Consider edge cases: null inputs, empty arrays, concurrent access
3. Check: Does this change break any existing interfaces?
4. Verify: Am I introducing security vulnerabilities? (SQL injection, XSS, etc.)
```

### Financial Operations

```
When processing financial transactions, use the think tool to:
1. Verify: Is the amount within authorized limits?
2. Check: Does the account have sufficient funds?
3. Validate: Are all compliance requirements met? (KYC, AML)
4. Confirm: Is this a duplicate of a recent transaction?

NEVER call transfer_funds() without a preceding think step.
```

## Think Tool vs Extended Thinking

These are complementary, not competing approaches.

| Aspect | Think Tool | Extended Thinking |
|--------|-----------|-------------------|
| **When it runs** | Mid-conversation, between tool calls | Before the first response token |
| **Best for** | Sequential decisions with consequences | Complex single-step reasoning |
| **Use case** | "Should I refund this order?" (needs policy check mid-chain) | "Solve this algorithm problem" (needs deep analysis upfront) |
| **Context** | Has access to all prior tool results | Has access to the full prompt |
| **Cost** | Adds ~100-500 tokens per think step | Uses dedicated thinking budget |
| **Control** | Agent decides when to use it | Always runs (if enabled) |

**Use both when:** Your agent needs deep initial planning (extended thinking) AND careful step-by-step decisions during execution (think tool). Example: a code migration agent that plans the migration strategy upfront, then carefully checks each file transformation against the plan.

## Performance Data

| Domain | Metric | Without Think Tool | With Think Tool | Improvement |
|--------|--------|--------------------|-----------------|:-----------:|
| Airline tau-bench | Task completion | 0.370 | 0.570 | **+54%** |
| Retail tau-bench | Task completion | 77.0% | 81.2% | +4.2% |
| SWE-bench Verified | Score | 0.614 | 0.623 (SOTA) | +1.6% |

**Key takeaway:** The improvement is largest in policy-heavy domains (airline: +54%) where the agent must check rules before acting. In domains with less policy complexity, the improvement is smaller but still positive.

## Implementation: Python

```python
import anthropic
import json

client = anthropic.Anthropic()

# Define the think tool
think_tool = {
    "name": "think",
    "description": "Use this tool to reason step-by-step before taking action. Your thoughts are private and not sent to external systems.",
    "input_schema": {
        "type": "object",
        "properties": {
            "thought": {
                "type": "string",
                "description": "Your step-by-step reasoning"
            }
        },
        "required": ["thought"]
    }
}

def handle_think_tool(thought: str) -> str:
    """Think tool handler — returns the thought as acknowledgment."""
    return json.dumps({"status": "ok", "thought_recorded": True})

def run_agent_with_think(system_prompt: str, tools: list, user_message: str) -> str:
    """Run an agent loop with the think tool included."""
    all_tools = [think_tool] + tools
    messages = [{"role": "user", "content": user_message}]

    while True:
        response = client.messages.create(
            model="claude-sonnet-4-6-20250514",
            max_tokens=4096,
            system=system_prompt,
            tools=all_tools,
            messages=messages,
        )

        # If no tool use, we're done
        if response.stop_reason == "end_turn":
            return response.content[0].text

        # Process tool calls
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                if block.name == "think":
                    # Think tool: just acknowledge
                    result = handle_think_tool(block.input["thought"])
                else:
                    # Real tool: execute it
                    result = execute_tool(block.name, block.input)

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result
                })

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})
```

## Implementation: TypeScript

```typescript
import Anthropic from "@anthropic-ai/sdk";

const client = new Anthropic();

const thinkTool: Anthropic.Tool = {
  name: "think",
  description:
    "Use this tool to reason step-by-step before taking action. Your thoughts are private and not sent to external systems.",
  input_schema: {
    type: "object" as const,
    properties: {
      thought: {
        type: "string",
        description: "Your step-by-step reasoning",
      },
    },
    required: ["thought"],
  },
};

async function runAgentWithThink(
  systemPrompt: string,
  tools: Anthropic.Tool[],
  userMessage: string
): Promise<string> {
  const allTools = [thinkTool, ...tools];
  const messages: Anthropic.MessageParam[] = [
    { role: "user", content: userMessage },
  ];

  while (true) {
    const response = await client.messages.create({
      model: "claude-sonnet-4-6-20250514",
      max_tokens: 4096,
      system: systemPrompt,
      tools: allTools,
      messages,
    });

    if (response.stop_reason === "end_turn") {
      const textBlock = response.content.find((b) => b.type === "text");
      return textBlock ? textBlock.text : "";
    }

    const toolResults: Anthropic.ToolResultBlockParam[] = [];
    for (const block of response.content) {
      if (block.type === "tool_use") {
        const result =
          block.name === "think"
            ? JSON.stringify({ status: "ok" })
            : await executeTool(block.name, block.input);

        toolResults.push({
          type: "tool_result",
          tool_use_id: block.id,
          content: result,
        });
      }
    }

    messages.push({ role: "assistant", content: response.content });
    messages.push({ role: "user", content: toolResults });
  }
}
```

## Implementation: Go

```go
package main

import (
	"context"
	"encoding/json"

	"github.com/anthropics/anthropic-sdk-go"
)

var thinkToolDef = anthropic.ToolDefinition{
	Name:        "think",
	Description: "Use this tool to reason step-by-step before taking action. Your thoughts are private.",
	InputSchema: json.RawMessage(`{
		"type": "object",
		"properties": {
			"thought": {
				"type": "string",
				"description": "Your step-by-step reasoning"
			}
		},
		"required": ["thought"]
	}`),
}

func runAgentWithThink(
	ctx context.Context,
	client *anthropic.Client,
	systemPrompt string,
	tools []anthropic.ToolDefinition,
	userMessage string,
) (string, error) {
	allTools := append([]anthropic.ToolDefinition{thinkToolDef}, tools...)
	messages := []anthropic.MessageParam{
		anthropic.UserMessage(userMessage),
	}

	for {
		resp, err := client.Messages.New(ctx, anthropic.MessageNewParams{
			Model:     "claude-sonnet-4-6-20250514",
			MaxTokens: 4096,
			System:    anthropic.SystemPrompt(systemPrompt),
			Tools:     allTools,
			Messages:  messages,
		})
		if err != nil {
			return "", err
		}

		if resp.StopReason == "end_turn" {
			for _, block := range resp.Content {
				if block.Type == "text" {
					return block.Text, nil
				}
			}
			return "", nil
		}

		var toolResults []anthropic.ContentBlockParam
		for _, block := range resp.Content {
			if block.Type == "tool_use" {
				var result string
				if block.Name == "think" {
					result = `{"status": "ok"}`
				} else {
					result = executeTool(block.Name, block.Input)
				}
				toolResults = append(toolResults, anthropic.ToolResult(block.ID, result))
			}
		}

		messages = append(messages,
			anthropic.AssistantMessage(resp.Content),
			anthropic.UserMessage(toolResults...),
		)
	}
}
```

## Agent Self-Reflection Patterns

The think tool enables several metacognitive patterns beyond simple reasoning.

### Pattern 1: Pre-Action Checklist

Prompt the agent to run through a checklist before high-stakes actions:

```
Before calling any tool that modifies data (create, update, delete), use the think tool to verify:
1. Do I have all required information?
2. Is this action reversible? If not, am I confident?
3. Have I confirmed the user's intent?
4. Could this action have unintended side effects?
```

### Pattern 2: Post-Action Evaluation

After completing a multi-step task, the agent evaluates its own work:

```
After completing a task, use the think tool to:
1. Did I address all parts of the user's request?
2. Are there edge cases I missed?
3. Is my output consistent with earlier decisions?
4. Would I do anything differently if I started over?
```

### Pattern 3: Uncertainty Acknowledgment

Teach the agent to recognize and communicate uncertainty:

```
If you are uncertain about any aspect of your response, use the think tool to:
1. Identify what specifically you're uncertain about
2. Rate your confidence (high/medium/low)
3. Decide: Should I proceed with a caveat, or ask for clarification?
```

### Pattern 4: Plan-Execute-Verify Loop

For complex tasks, the agent plans, executes, then verifies:

```
For multi-step tasks:
1. PLAN: Use think tool to outline your approach (all steps)
2. EXECUTE: Carry out each step, using think between steps to verify progress
3. VERIFY: Use think tool to check if the final result matches the plan
```

## Common Mistakes

| Mistake | Why It's Bad | Fix |
|---------|-------------|-----|
| Adding think tool to simple agents | Adds latency and cost for no benefit | Only add for > 3 tool calls or policy decisions |
| Not prompting when to use it | Agent never calls it voluntarily | Add explicit instructions in system prompt |
| Think tool with no context | "Let me think..." (empty reasoning) | Prompt for specific checks: policy, prerequisites, tradeoffs |
| Using think tool instead of extended thinking | Wrong tool for the job | Use extended thinking for upfront analysis, think tool for mid-chain reasoning |
