# Vanilla Python

For agents written without a framework. Two lines of code give your agent persistent memory across restarts, processes, and machines.

**Requires:** Python 3.9+, octopoda 3.1.4+
**Setup time:** 2 minutes
**Prerequisite:** Finish the Getting started guide first so your API key is set. Without a key, this still works but writes to a local SQLite file instead of Octopoda Cloud.

## Install

If you completed Getting started, you already have this:

```
pip install octopoda
```

## Two-line integration

Add this to the top of your agent script:

```python
from octopoda import AgentRuntime

agent = AgentRuntime("your_agent_id")
```

That's the integration. You now have an agent with persistent memory. Everything below is how to use it.

## Choosing your agent_id

The string you pass to `AgentRuntime()` is your agent's identity. Memory is scoped to this string. Use the same value every time you start your script, or you'll create a brand-new agent with empty memory.

Three common patterns:

**One agent per user** (chatbots, personal assistants):

```python
agent = AgentRuntime(f"user_{user_id}")
```

**One agent per role** (support bot, research bot):

```python
agent = AgentRuntime("customer_support_bot")
```

**One agent per conversation** (short-lived sessions):

```python
agent = AgentRuntime(f"conversation_{session_uuid}")
```

### Rules for agent_id

- Must be a non-empty string
- Case-sensitive ("MyBot" and "mybot" are two different agents)
- No whitespace stripping ("bot " and "bot" are two different agents)
- Stable across runs — if you're using f-strings, make sure the variable is deterministic

### Multiple agents in one script

You can create as many agents as you want. Each has independent memory:

```python
support = AgentRuntime("support_bot")
research = AgentRuntime("research_bot")

support.remember("active_ticket", "T-1234")
research.remember("active_topic", "quantum computing")

support.recall("active_topic").found   # False — different agent
research.recall("active_topic").value  # "quantum computing"
```

## Storing memories (remember)

Anywhere in your code:

```python
agent.remember("key", "value")
```

### What can `value` be?

Anything JSON-serialisable:

```python
agent.remember("user_name", "Alex")                         # string
agent.remember("ticket_count", 42)                          # int
agent.remember("preferences", {"lang": "en", "tz": "GMT"})  # dict
agent.remember("recent_orders", [1001, 1002, 1003])         # list
```

Octopoda stores values verbatim and returns them unchanged on recall. You can nest structures up to any reasonable depth.

### Key naming convention

Keys are just strings, but a namespace-like structure with colons makes your memory easier to browse in the dashboard:

```python
agent.remember("user:name", "Alex")
agent.remember("user:email", "alex@example.com")
agent.remember("task:current", "process_refund")
```

No enforcement, but most users adopt this pattern.

### What `remember` returns

```python
result = agent.remember("user:name", "Alex")
# MemoryResult(node_id=..., key="user:name", success=True, latency_us=...)
```

You rarely need to check it. Failures raise exceptions (network errors, quota exceeded, etc.), not silent `success=False`. Check for exceptions if you need error handling.

## Reading memories (recall)

```python
result = agent.recall("key")
```

`result` is a `RecallResult` with four fields:

- `result.value` — the stored value, or `None` if the key doesn't exist
- `result.found` — `True` if the key exists, `False` if not
- `result.key` — echo of the key you asked for
- `result.latency_us` — how long the recall took, in microseconds

### Always check `.found` before using `.value`

If the key doesn't exist, `value` is `None`. Using it unchecked can crash:

```python
name = agent.recall("user:name")

# Wrong — crashes if never stored
print(name.value.upper())

# Right
if name.found:
    print(name.value.upper())
else:
    print("user hasn't introduced themselves yet")
```

## Forgetting memories

To delete a memory:

```python
result = agent.forget("user:name")
# {'key': 'user:name', 'deleted': True, 'reason': 'explicit_forget'}
```

`deleted` is `False` only if the key didn't exist. No exception is raised.

## Thread safety

`AgentRuntime` is safe to share across threads. This is common in web servers:

```python
from flask import Flask, request
from octopoda import AgentRuntime

app = Flask(__name__)
agent = AgentRuntime("web_app")  # one instance, shared

@app.route("/remember", methods=["POST"])
def store():
    data = request.json
    agent.remember(data["key"], data["value"])
    return "ok"
```

Parallel writes from multiple requests are serialised correctly. Tested up to 100 concurrent writes per second with 100% persistence.

## Semantic search (optional)

The core install gives you exact-key lookups via `recall`. For searching memories by meaning rather than exact key, install the AI extra:

```
pip install "octopoda[ai]"
```

Then:

```python
result = agent.recall_similar("what language does the user speak?", limit=3)
for item in result.items:
    print(item["key"], item["value"], item["score"])
```

### When to use `recall_similar` vs `recall` vs `search`

| You want to... | Use |
|---|---|
| Find a specific value by exact key | `agent.recall("user:name")` |
| Find keys starting with a prefix | `agent.search("user:")` |
| Find memories by meaning | `agent.recall_similar("what is the user's language?")` |

`recall` is instant (under 100ms) and free.
`search` is instant and free.
`recall_similar` needs the `[ai]` extra installed, uses embeddings, and takes ~100-200ms.

## Running two sessions — proving persistence

The clearest demo that memory survives process restarts is to put it in two separate files.

**session_1.py:**

```python
from octopoda import AgentRuntime

agent = AgentRuntime("triage_bot")
agent.remember("user:name", "Alex")
agent.remember("user:preferred_language", "en-GB")
print("stored")
```

**session_2.py** (run AFTER session_1.py has exited):

```python
from octopoda import AgentRuntime

agent = AgentRuntime("triage_bot")
name = agent.recall("user:name")
if name.found:
    print(f"Welcome back, {name.value}!")
else:
    print("No user stored yet.")
```

Run them in sequence:

```
python session_1.py
# output: stored

python session_2.py
# output: Welcome back, Alex!
```

If session_2.py prints "Welcome back, Alex!", your agent has true cross-process memory. If it says "No user stored yet", either your agent_id doesn't match between runs, or your environment variable isn't being picked up by the second run. Re-run the sanity check from Getting started.

## Local mode vs cloud mode

If `OCTOPODA_API_KEY` is set in your environment, `AgentRuntime` uses cloud storage (Octopoda Cloud on our servers). If it's NOT set, everything above still works — writes go to `~/.synrix/data/synrix.db` on your local machine.

No code change is needed to switch between modes. The same script works both ways. Upgrade from local to cloud by setting the env var whenever you're ready.

## Full working example

A single file showing a typical usage pattern:

```python
from octopoda import AgentRuntime

def greet_user(user_id: str) -> str:
    agent = AgentRuntime(f"user_{user_id}")

    name = agent.recall("user:name")
    if name.found:
        return f"Welcome back, {name.value}!"
    return "Hi there! What's your name?"

def remember_name(user_id: str, name: str):
    agent = AgentRuntime(f"user_{user_id}")
    agent.remember("user:name", name)

# On first visit:
print(greet_user("u123"))  # "Hi there! What's your name?"
remember_name("u123", "Alex")

# On next visit, even hours later, in a fresh process:
print(greet_user("u123"))  # "Welcome back, Alex!"
```

## Common mistakes

**Forgetting to check `.found`**

```python
agent.recall("user:name").value.upper()
# AttributeError if never stored. Check .found first.
```

**Using a different agent_id between runs**

```python
# File A
AgentRuntime("customer_bot").remember("x", "y")

# File B
AgentRuntime("customerBot").recall("x").found  # False — different agent
```

Case and whitespace matter.

**Assuming `recall_similar` works without `[ai]` extras**

```python
# Without octopoda[ai] installed:
agent.recall_similar("query")
# Returns empty SearchResult. No error, just no results.
```

Install the extra if you need semantic search: `pip install "octopoda[ai]"`.

**Treating `recall_similar` results like a plain list**

```python
# Wrong:
for h in agent.recall_similar("query"):
    print(h.key)
# TypeError — SearchResult is not iterable, .items is.

# Right:
result = agent.recall_similar("query")
for item in result.items:
    print(item["key"])
```

## Next step

You now have persistent memory. Most users stop here — Vanilla Python is all they need.

If you use a framework (LangChain, CrewAI, AutoGen, OpenAI Agents), the framework-specific guide is a thin layer on top of what you just learned. Read those if you want framework integration.
