# Managed Agents Reference

## What Is a Managed Agent?

A managed agent is an agent run as a hosted service rather than as a single process owned by its user. It must survive worker crashes, scale horizontally, stay secure across tenants, and let its operator swap models without restarting sessions. These requirements push the architecture toward three decoupled pieces:

```
         Session (durable event log — OUTSIDE the context window)
                     ^                        ^
                     | getEvents              | appendEvent
                     |                        |
         +-----------+-----------+  +---------+-----------+
         |   Harness (brain)     |  |   Sandbox (hands)   |
         |   stateless model loop|  |   execute(name,in)  |
         +-----------------------+  +---------------------+
```

- **Session** — append-only log of every event (user input, model turn, tool call, tool result). The source of truth. Lives in durable storage, not in the model's context window.
- **Harness** — the model loop. Reads events, builds context, calls the model, dispatches tool calls, writes events. Carries no state across turns.
- **Sandbox** — the execution environment for tool calls. Exposes exactly one operation: `execute(name, input) -> string`. Holds credentials the model must never see.

If you can't name which piece a given responsibility belongs to, you haven't decoupled cleanly yet.

## When to Adopt This Architecture

**Adopt when you have any of these:**
- Sessions that run for minutes to hours and must survive process restarts
- Multi-tenant service with isolation requirements per user
- A fleet of workers you need to scale or patch independently of session state
- Plans to A/B models or swap model versions mid-session
- Heavy-tool agents that want several parallel sandboxes reasoned about by one model

**Don't adopt when:**
- You're building a CLI tool one user runs locally — a process plus a file is enough
- Your agent completes in under a minute and holds no state anyone cares about
- You haven't yet proven the agent works in-memory — the single-process version is what teaches you which seams to cut

A managed agent is a distributed system. Don't pay that cost until you need it.

## The Three Components

### Session: The Event Log

A session is an append-only sequence of events. Nothing in the session can be mutated — only appended to. Compaction and summaries are themselves events.

**Minimal event schema:**
```python
@dataclass
class Event:
    id: str                      # monotonic, per-session
    session_id: str
    kind: str                    # "user" | "assistant" | "tool_use" | "tool_result" | "system" | "compaction"
    payload: dict                # shape depends on kind
    created_at: datetime
    parent_id: str | None        # tool_result -> tool_use linkage
```

**Session API (minimum surface):**
```python
class SessionStore:
    def create(self, tenant_id: str) -> str: ...
    def append_event(self, session_id: str, event: Event) -> None: ...
    def get_events(self, session_id: str, since: str | None = None) -> list[Event]: ...
    def get(self, session_id: str) -> SessionState: ...  # status, heartbeat, metadata
    def mark_complete(self, session_id: str) -> None: ...
```

**Why append-only?** Replay. The session is the ground truth context. Given the same log, any harness should reconstruct the same messages. Mutability breaks that guarantee and makes crash recovery unsafe.

**What lives in events vs. the context window:** The log can be gigabytes. The context window is bounded. The harness is responsible for deciding what slice of the log becomes context this turn — typically recent events plus summaries of older ones. The session is durable memory; the context is the working set.

### Harness: The Stateless Brain

The harness is one turn of a model loop: read events, build context, call the model, dispatch tool calls, write events. That's it. It holds no state across turns.

**Canonical turn:**
```python
def run_turn(session_id: str) -> None:
    events = session.get_events(session_id)
    messages = rebuild_context(events)        # events -> Anthropic messages

    response = client.messages.create(
        model=pick_model(session_id),          # can change between turns
        tools=TOOL_SPECS,
        messages=messages,
        max_tokens=4096,
    )

    session.append_event(session_id, Event(kind="assistant", payload={"content": response.content}))

    tool_uses = [b for b in response.content if b.type == "tool_use"]
    for block in tool_uses:
        session.append_event(session_id, Event(kind="tool_use", payload=block.model_dump()))
        result = sandbox.execute(block.name, block.input)
        session.append_event(session_id, Event(
            kind="tool_result",
            payload={"tool_use_id": block.id, "output": result},
            parent_id=block.id,
        ))

    if response.stop_reason == "end_turn":
        session.mark_complete(session_id)
    elif tool_uses:
        enqueue(session_id)                    # schedule the next turn
```

**Context rebuild:**
```python
def rebuild_context(events: list[Event]) -> list[dict]:
    messages = []
    for e in events:
        if e.kind == "user":
            messages.append({"role": "user", "content": e.payload["text"]})
        elif e.kind == "assistant":
            messages.append({"role": "assistant", "content": e.payload["content"]})
        elif e.kind == "tool_result":
            messages.append({"role": "user", "content": [{
                "type": "tool_result",
                "tool_use_id": e.payload["tool_use_id"],
                "content": e.payload["output"],
            }]})
        elif e.kind == "compaction":
            # fold older events into a system summary
            messages.insert(0, {"role": "system", "content": e.payload["summary"]})
    return messages
```

**Why stateless?** Any worker must be able to pick up any session. If the harness caches anything that isn't derivable from the log — a plan it only wrote to memory, a scratch pad, a "last decision" — then crashing the worker loses work. Stateless harnesses turn session ownership into a scheduling problem, not a coordination problem.

### Sandbox: The Hands

The sandbox exposes a single narrow contract:
```python
def execute(name: str, input: dict) -> str: ...
```

Everything the agent "does" — reading a file, running a command, calling an API, editing code — goes through this function. The return is a string (or structured JSON serialized as a string) that becomes a tool result.

**Why so narrow?** The contract is a trust boundary. The smaller the surface, the smaller the blast radius when something inside misbehaves. Sandboxes are replaceable — Docker today, Firecracker tomorrow, an MCP worker next month — as long as they implement `execute`.

**What belongs inside:**
- Filesystem with per-session isolation
- Network egress via an allowlist
- Tool implementations (git, bash, file edits, HTTP)
- Ephemeral caches and scratch space

**What does NOT belong inside:**
- Long-lived credentials (tokens, API keys, customer secrets)
- Other tenants' data
- Anything that would be catastrophic if the model convinced itself to exfiltrate it

## Crash Recovery Protocol

Because the harness is stateless and the session is durable, recovery is "pick up where we left off".

```python
STALE_SECONDS = 60

def wake(session_id: str) -> None:
    """Idempotent resumption. Safe to call from any worker."""
    state = session.get(session_id)

    if state.status == "complete":
        return
    if state.status == "running" and state.last_heartbeat > now() - STALE_SECONDS:
        return  # a live worker owns it

    # Claim ownership atomically (lease, compare-and-swap, or advisory lock)
    if not session.try_claim(session_id, worker_id=self.id):
        return

    try:
        run_turn(session_id)
    finally:
        session.release(session_id)


def heartbeat_loop(session_id: str) -> None:
    """While run_turn is in flight, keep the lease alive."""
    while True:
        session.heartbeat(session_id)
        time.sleep(STALE_SECONDS / 3)
```

**Invariants this relies on:**
1. Every side effect on the sandbox is accompanied by an event in the session log (write-ahead). If a worker crashes between the side effect and the event append, the next worker sees no event and may re-execute — so sandbox tools should be idempotent where possible (e.g., use commit SHAs, not "apply the patch again").
2. Leases prevent two workers from running the same turn. Heartbeats prevent a crashed worker from holding the lease forever.
3. `run_turn` is retry-safe when called at the same event offset. Append-only events + compare-and-swap on `next_event_id` give you this.

## Security Model

The sandbox is where the agent's generated actions run, which is also where prompt injection lands. The security model assumes the sandbox is hostile.

### Credentials never enter the sandbox as plaintext

**Wrong:**
```python
# Git token exposed to every subsequent tool call
os.environ["GITHUB_TOKEN"] = user_token
sandbox.execute("bash", {"cmd": "git clone https://github.com/org/repo"})
```

**Right:**
```python
# Token is used by the control plane to do the clone, then scrubbed
clone_url = inject_token_for_clone(user_token, repo)    # short-lived URL
sandbox.execute("internal.git_clone", {"url": clone_url})
# Inside the sandbox, `.git/config` is rewritten to a credential-less remote
# before any agent tool call can run
```

### MCP and third-party API calls go through a proxy

The sandbox sees `execute("slack.post_message", {...})`. The MCP proxy — outside the sandbox — attaches the OAuth token server-side. The agent can invoke the capability but cannot read the secret that authorizes it.

```
Sandbox ---- JSON RPC ----> MCP Proxy ----+ OAuth token (held server-side)
                                          |
                                          v
                                    Slack / Jira / etc.
```

### The tool contract is the trust boundary

Everything inside the sandbox is replaceable and disposable. Everything outside is trusted. Things that look like convenience — a shared cache, an env var "just for this tool", an unsandboxed subprocess — are holes in that boundary.

## Scaling Patterns

Decoupling lets different pieces scale on different signals.

### Many brains, one hand pool

Cheap routing or classification harnesses can share a pool of sandboxes. The sandbox is reused across short-lived turns; the brain spins up per request.

```
Harness-A ->\
Harness-B ---> [Sandbox pool: warm containers]
Harness-C ->/
```

Use when: latency matters more than isolation (e.g., short interactive agents), and sandboxes are stateless between turns.

### One brain, many hands

The model holds a plan in context and fans out work across several sandboxes. The harness surfaces sandbox IDs to the model; the model reasons about which sandbox to dispatch each action to.

```
                 [Harness/brain]
                 /     |      \
                v      v       v
           sandbox-1  sandbox-2  sandbox-3
           (service   (service   (frontend
            A repo)    B repo)    repo)
```

Use when: a task touches isolated environments concurrently — e.g., a migration that touches three services and you want independent filesystems, blast radiuses, and test runs.

### Brain swap mid-session

Because the session is the source of truth, switching models is just a change in which harness picks up the next turn. You can run Haiku for the planning phase and Opus for the execution phase of the same session, or upgrade a long-running session to a new model version without restarting.

## Operational Metrics That Matter

| Metric | What it tells you | Target shape |
|--------|-------------------|--------------|
| **TTFT (time to first token) p50 / p95** | How responsive the harness feels | p50 seconds, p95 within small multiple of p50 |
| **Turn latency** | End-to-end time to advance one event | Driven by model + sandbox, not queue waits |
| **Session resume success rate** | Crash recovery is working | > 99%; investigate any double-execution events |
| **Sandbox cold-start time** | How much you pay for isolation | Seconds, amortized via pooling |
| **Events per session p50 / p99** | How much context you're managing | Watch for runaway loops in the tail |
| **Lease contention rate** | Two workers fighting for one session | Near zero; spikes indicate heartbeat tuning |

**Case study context:** After moving to this architecture, one reported rollout saw p50 TTFT drop 60% and p95 TTFT drop 90%, with sessions that previously died on worker crashes now resuming on a different worker within seconds.

## Common Anti-Patterns

| Anti-pattern | Symptom | Fix |
|--------------|---------|-----|
| Stateful harness ("just cache the plan in memory") | Recovery silently drops work | Derive everything from events; cache only within a single `run_turn` call |
| Wide sandbox API (`execute`, plus `upload`, `stream`, `getEnv`...) | Each new method is a new security review | Collapse back to `execute(name, input) -> string`; tunneled operations become tools |
| Credentials in env vars | Prompt injection can exfiltrate tokens | Proxy auth server-side; inject scoped URLs, not secrets |
| Mutable session log | Replay is non-deterministic | Append-only; compactions are themselves events |
| Tool output not idempotent | Double-execution on retry corrupts state | Use content-addressed operations (commit SHAs, idempotency keys) |
| Carrying harness hacks across model versions | Yesterday's workaround is today's bug | Re-run harness behaviors against each new model; delete what's no longer needed (e.g., context-anxiety wrap-up logic) |

## Model-Drift Maintenance

Harness code accumulates workarounds for model behaviors — over-eager compaction, "context anxiety" near the window limit, premature wrap-up. Those behaviors move between model versions. A workaround that was essential for Sonnet 4.5 may do nothing, or do harm, on Opus 4.5.

**Maintenance ritual, each model bump:**
1. Enumerate the harness's "because the model does X" branches in a list.
2. For each, re-run the eval scenario that justified it.
3. Keep it only if the new model still does X; delete it otherwise.
4. Check evals for new behaviors the harness does not yet handle.

Harnesses are software; they decay. Schedule the review.

## Minimal Checklist Before Shipping

```
[ ] Session log is append-only; compactions are events, not rewrites
[ ] Harness holds zero cross-turn state; any worker can resume any session
[ ] Sandbox API is exactly one operation: execute(name, input) -> string
[ ] Credentials never enter the sandbox; proxies attach auth server-side
[ ] Every side effect has a preceding write-ahead event
[ ] Crash recovery exercised: kill -9 a worker mid-turn; session completes
[ ] Lease + heartbeat tuned so a dead worker releases within seconds
[ ] Evals cover resumed sessions, not only fresh ones
[ ] Harness workaround list tracked per model version
[ ] Metrics: TTFT p50/p95, resume success rate, lease contention, events per session
```

## Related Patterns

- Pattern 8 in `patterns-reference.md` — the short, decision-oriented version of this architecture.
- `context-engineering-reference.md` — the session log is durable memory; context engineering decides what slice becomes working set each turn.
- `tool-design-reference.md` — sandbox tools are the contract between model and environment; the narrower, the safer.
- `evals-reference.md` — add crash-recovery and long-session evals; see the "Infrastructure Noise" section for why eval resource config matters.
