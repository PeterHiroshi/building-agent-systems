"""
Research Agent — Prompt Chain Pattern

A beginner-friendly agent that researches a topic using a 3-step prompt chain:
1. Search for relevant information
2. Extract key facts with evidence
3. Synthesize into a structured summary

Each step has a validation gate that catches failures early.
"""

import anthropic
import json
import sys

client = anthropic.Anthropic()
MODEL = "claude-sonnet-4-6-20250514"

# --- Tool Definitions ---

tools = [
    {
        "name": "web_search",
        "description": (
            "Search the web for information on a topic. "
            "Use this when you need to find current information, facts, or sources. "
            "Returns a list of search results with titles, snippets, and URLs.\n\n"
            "Example: web_search(query='quantum computing breakthroughs 2024')"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query — be specific for better results",
                },
                "num_results": {
                    "type": "integer",
                    "description": "Number of results to return (default: 5, max: 10)",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    }
]


def mock_web_search(query: str, num_results: int = 5) -> dict:
    """Mock search results for demonstration. Replace with a real search API."""
    return {
        "results": [
            {
                "title": f"Result about: {query}",
                "snippet": f"This is a mock search result for '{query}'. In production, connect this to a real search API like Brave Search, SerpAPI, or Tavily.",
                "url": f"https://example.com/article-about-{query.replace(' ', '-')}",
            }
            for i in range(min(num_results, 5))
        ],
        "total_results": num_results,
    }


def execute_tool(name: str, input_data: dict) -> str:
    """Execute a tool call and return the result as a string."""
    if name == "web_search":
        result = mock_web_search(
            input_data["query"], input_data.get("num_results", 5)
        )
        return json.dumps(result)
    return json.dumps({"error": f"Unknown tool: {name}"})


# --- Agent Steps ---


def step_search(topic: str) -> str | None:
    """Step 1: Search for information on the topic."""
    messages = [
        {
            "role": "user",
            "content": f"Search for recent, authoritative information about: {topic}\n\nMake 1-2 targeted searches to find the most relevant sources.",
        }
    ]

    # Run agent loop until search is complete
    search_results = []
    for _ in range(5):  # Max 5 rounds
        response = client.messages.create(
            model=MODEL, max_tokens=1024, tools=tools, messages=messages
        )

        # Collect tool calls
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result = execute_tool(block.name, block.input)
                search_results.append(result)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    }
                )

        if response.stop_reason == "end_turn":
            # Agent is done searching — return the text summary
            text_blocks = [b for b in response.content if b.type == "text"]
            return text_blocks[0].text if text_blocks else None

        # Continue the loop
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

    return None


def step_extract_facts(search_summary: str) -> str | None:
    """Step 2: Extract key facts with evidence from the search results."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        messages=[
            {
                "role": "user",
                "content": f"""Extract 5-10 key facts from this research. For each fact:
- State the fact clearly in one sentence
- Include a direct quote or specific data point as evidence
- Note the source

Research:
{search_summary}

Return as a numbered list. Each item should have: Fact, Evidence, Source.""",
            }
        ],
    )
    return response.content[0].text


def step_synthesize(facts: str, topic: str) -> str | None:
    """Step 3: Synthesize facts into a structured summary."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        messages=[
            {
                "role": "user",
                "content": f"""Synthesize these facts into a structured research summary.

Topic: {topic}
Facts:
{facts}

Structure your summary as:
1. Overview (2-3 sentences)
2. Key Findings (3-5 bullet points)
3. Notable Details (anything surprising or important)
4. Sources (list of sources referenced)""",
            }
        ],
    )
    return response.content[0].text


# --- Main Agent ---


def research_agent(topic: str) -> dict:
    """
    Research a topic using a 3-step prompt chain.

    Returns:
        dict with 'summary', 'facts', and 'topic' on success
        dict with 'error' and 'step' on failure
    """
    print(f"Researching: {topic}\n")

    # Step 1: Search
    print("Step 1: Searching for information...")
    search_summary = step_search(topic)

    # Gate 1: Did we find anything?
    if not search_summary or len(search_summary) < 50:
        return {"error": "Search returned insufficient results", "step": 1}
    print(f"  Found information ({len(search_summary)} chars)\n")

    # Step 2: Extract facts
    print("Step 2: Extracting key facts...")
    facts = step_extract_facts(search_summary)

    # Gate 2: Did we extract meaningful facts?
    if not facts or len(facts) < 100:
        return {"error": "Fact extraction produced insufficient results", "step": 2}
    print(f"  Extracted facts ({len(facts)} chars)\n")

    # Step 3: Synthesize
    print("Step 3: Synthesizing summary...")
    summary = step_synthesize(facts, topic)

    if not summary:
        return {"error": "Synthesis failed", "step": 3}
    print("  Summary complete\n")

    return {"summary": summary, "facts": facts, "topic": topic}


if __name__ == "__main__":
    topic = sys.argv[1] if len(sys.argv) > 1 else "recent advances in AI agents"
    result = research_agent(topic)

    if "error" in result:
        print(f"\nFailed at step {result['step']}: {result['error']}")
    else:
        print("=" * 60)
        print("RESEARCH SUMMARY")
        print("=" * 60)
        print(result["summary"])
