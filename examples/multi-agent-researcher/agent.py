"""
Multi-Agent Researcher — Orchestrator-Workers Pattern

An advanced agent that:
1. Orchestrator (Opus) analyzes a complex question and creates parallel subtasks
2. Workers (Sonnet) execute each subtask independently
3. Orchestrator synthesizes all worker results into a coherent report

Demonstrates graceful degradation when workers fail.
"""

import anthropic
import asyncio
import json
import sys
import time

client = anthropic.Anthropic()

ORCHESTRATOR_MODEL = "claude-sonnet-4-6-20250514"  # Use Opus in production for complex planning
WORKER_MODEL = "claude-sonnet-4-6-20250514"

# --- Orchestrator ---

ORCHESTRATOR_PLAN_PROMPT = """You are a research orchestrator. Your job is to break complex research questions into parallel subtasks.

Given a research question:
1. Identify 3-5 independent research subtasks that can be executed in parallel
2. Each subtask should be self-contained (no dependencies on other subtasks)
3. Each subtask should be specific and bounded

Return a JSON array of subtask descriptions. Each subtask should be a string
that a researcher can work on independently.

Example output:
["Research the history of X", "Compare current approaches to Y", "Analyze the economic impact of Z"]

Return ONLY the JSON array, no other text."""

ORCHESTRATOR_SYNTHESIS_PROMPT = """You are a research orchestrator. Synthesize these worker results into a coherent research report.

IMPORTANT: Synthesize, don't concatenate. Find themes, resolve contradictions, and produce a unified narrative.

Structure your report as:
## Executive Summary
[2-3 sentences capturing the key findings]

## Key Findings
[Organized by theme, not by worker]

## Analysis
[Cross-cutting insights from combining the research]

## Gaps and Limitations
[What we couldn't fully answer, contradictions found]

## Conclusion
[Bottom-line answer to the original question]"""

# --- Worker ---

WORKER_PROMPT = """You are a specialist researcher. Complete ONLY the assigned research task.

Return your findings as JSON with this structure:
{
    "findings": ["finding 1", "finding 2", ...],
    "key_insight": "The most important takeaway",
    "confidence": "high|medium|low",
    "gaps": ["What you couldn't find or verify"]
}

Be thorough but focused. Only research the specific task assigned to you.
Return ONLY the JSON, no other text."""


def plan_subtasks(question: str) -> list[str]:
    """Orchestrator plans the research by creating subtasks."""
    response = client.messages.create(
        model=ORCHESTRATOR_MODEL,
        max_tokens=1024,
        system=ORCHESTRATOR_PLAN_PROMPT,
        messages=[{"role": "user", "content": f"Research question: {question}"}],
    )

    try:
        return json.loads(response.content[0].text)
    except json.JSONDecodeError:
        # Fallback: treat the whole question as a single task
        return [question]


def execute_worker(subtask: str, worker_id: int) -> dict:
    """Execute a single worker on a subtask."""
    print(f"  Worker {worker_id}: Starting — {subtask[:60]}...")
    start = time.time()

    try:
        response = client.messages.create(
            model=WORKER_MODEL,
            max_tokens=2048,
            system=WORKER_PROMPT,
            messages=[
                {"role": "user", "content": f"Research task: {subtask}"}
            ],
        )

        duration = time.time() - start
        result_text = response.content[0].text

        try:
            result = json.loads(result_text)
        except json.JSONDecodeError:
            result = {
                "findings": [result_text],
                "key_insight": "See findings",
                "confidence": "medium",
                "gaps": ["Result was not structured JSON"],
            }

        print(
            f"  Worker {worker_id}: Done ({duration:.1f}s, "
            f"{len(result.get('findings', []))} findings, "
            f"confidence: {result.get('confidence', 'unknown')})"
        )
        return {"worker_id": worker_id, "subtask": subtask, "result": result, "status": "success"}

    except Exception as e:
        duration = time.time() - start
        print(f"  Worker {worker_id}: FAILED ({duration:.1f}s) — {e}")
        return {
            "worker_id": worker_id,
            "subtask": subtask,
            "result": None,
            "status": "failed",
            "error": str(e),
        }


def synthesize_results(question: str, worker_results: list[dict]) -> str:
    """Orchestrator synthesizes all worker results."""
    successes = [r for r in worker_results if r["status"] == "success"]
    failures = [r for r in worker_results if r["status"] == "failed"]

    results_text = ""
    for r in successes:
        results_text += f"\n### Subtask: {r['subtask']}\n"
        results_text += json.dumps(r["result"], indent=2)
        results_text += "\n"

    failure_note = ""
    if failures:
        failure_note = f"\n\nNote: {len(failures)} worker(s) failed. The following subtasks were not completed:\n"
        for f in failures:
            failure_note += f"- {f['subtask']}\n"

    response = client.messages.create(
        model=ORCHESTRATOR_MODEL,
        max_tokens=4096,
        system=ORCHESTRATOR_SYNTHESIS_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"""Original question: {question}

Worker results ({len(successes)} successful, {len(failures)} failed):
{results_text}
{failure_note}

Synthesize these findings into a coherent research report.""",
            }
        ],
    )
    return response.content[0].text


# --- Main Agent ---


def multi_agent_researcher(question: str) -> dict:
    """
    Research a complex question using the orchestrator-workers pattern.

    Returns:
        dict with 'report', 'subtasks', 'worker_count', 'failures'
    """
    print(f"Research question: {question}\n")

    # Phase 1: Plan
    print("Phase 1: Planning subtasks...")
    subtasks = plan_subtasks(question)
    print(f"  Created {len(subtasks)} subtasks:\n")
    for i, task in enumerate(subtasks):
        print(f"  {i + 1}. {task}")
    print()

    # Phase 2: Execute workers (sequentially in this example; use asyncio for parallel)
    print("Phase 2: Executing workers...")
    start = time.time()
    worker_results = []
    for i, subtask in enumerate(subtasks):
        result = execute_worker(subtask, i + 1)
        worker_results.append(result)

    worker_duration = time.time() - start
    successes = sum(1 for r in worker_results if r["status"] == "success")
    failures = sum(1 for r in worker_results if r["status"] == "failed")
    print(f"\n  All workers complete: {successes} succeeded, {failures} failed ({worker_duration:.1f}s)\n")

    # Phase 3: Synthesize
    print("Phase 3: Synthesizing results...")
    report = synthesize_results(question, worker_results)

    return {
        "report": report,
        "subtasks": subtasks,
        "worker_count": len(subtasks),
        "successes": successes,
        "failures": failures,
    }


if __name__ == "__main__":
    question = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "What are the main approaches to building reliable AI agent systems, and what are the tradeoffs between them?"
    )

    result = multi_agent_researcher(question)

    print("=" * 60)
    print("RESEARCH REPORT")
    print("=" * 60)
    print(result["report"])
    print(f"\n--- {result['worker_count']} workers, {result['failures']} failures ---")
