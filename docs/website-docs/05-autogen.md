# AutoGen

AutoGen organises around group chats, so Octopoda memory is group-scoped. Store every message and replay the conversation in any future run.

**Requires:** Python 3.9+, octopoda 3.1.4+, autogen-agentchat 0.7+
**Setup time:** 3 minutes
**Prerequisite:** Finish Getting started so your API key is set.

## Install

Use the modern autogen-agentchat package. The older `pyautogen` package is deprecated and not supported.

```
pip install octopoda autogen-agentchat autogen-core
```

For the OpenAI model client used in the full example:

```
pip install "autogen-ext[openai]"
```

Your LLM also needs its own key:

```
export OPENAI_API_KEY=sk-...
```

## Two-step integration

### Step 1 — Import the memory bus

```python
from octopoda import AutoGenMemory
```

### Step 2 — Create it with your group_id

```python
memory = AutoGenMemory(group_id="your_group_id")
```

The argument is `group_id`, not `agent_id`. Passing `agent_id=` will raise `TypeError: got an unexpected keyword argument 'agent_id'`.

`group_id` identifies one group chat configuration. Use the same value every run of the same team.

## Store messages as they happen

After each message event in your group chat:

```python
memory.store_message(sender, recipient, content)
```

All three arguments are strings, all three are positional (or pass as keywords for clarity):

- `sender` — agent name that sent the message
- `recipient` — target agent name, or `"group"` for broadcasts
- `content` — the message text

### When to use "group" vs a specific agent name

In RoundRobinGroupChat and similar broadcast patterns, every agent sees every message. Use `"group"` as recipient.

In targeted multi-agent setups where you want who-said-what-to-whom tracking, pass the specific target agent's name.

## Retrieve in a later run

```python
memory = AutoGenMemory(group_id="your_group_id")
history = memory.get_conversation_history()

for m in history:
    print(f"{m['sender']} to {m['recipient']}: {m['content']}")
```

Each message is a dict with `sender`, `recipient`, `content`, and a timestamp field.

## Other useful methods

```python
# Semantic search within the conversation
memory.search_conversations("user's preferences")

# All messages a specific agent sent or received
memory.get_agent_knowledge("planner")

# Export whole conversation as text/JSON
memory.export_conversation()

# Conversation statistics
memory.get_stats()
# {'message_count': 42, 'unique_agents': 3, ...}
```

## Full working example

```python
import asyncio
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import MaxMessageTermination
from autogen_ext.models.openai import OpenAIChatCompletionClient
from octopoda import AutoGenMemory

memory = AutoGenMemory(group_id="research_team")

# Replay prior conversation, if any
for m in memory.get_conversation_history():
    print(f"[history] {m['sender']} -> {m['recipient']}: {m['content']}")

model = OpenAIChatCompletionClient(model="gpt-4o-mini")

planner = AssistantAgent("planner", model_client=model,
    system_message="Plan tasks concisely.")
worker = AssistantAgent("worker", model_client=model,
    system_message="Execute tasks concisely.")

team = RoundRobinGroupChat(
    [planner, worker],
    termination_condition=MaxMessageTermination(max_messages=4),
)

async def run():
    async for event in team.run_stream(task="Plan and execute: research AI memory tools"):
        if hasattr(event, 'source') and hasattr(event, 'content'):
            memory.store_message(
                sender=str(event.source),
                recipient="group",
                content=str(event.content),
            )

asyncio.run(run())

# After the run, inspect what was stored
print(f"Stored {len(memory.get_conversation_history())} messages")
```

## Cross-process persistence

The simplest proof that memory survives restarts: run the example above, print `len(memory.get_conversation_history())` — say 4 messages. Then quit Python, open a new process:

```python
from octopoda import AutoGenMemory
memory = AutoGenMemory(group_id="research_team")
print(len(memory.get_conversation_history()))
# 4
```

Same count, no loss. Memory persisted.

## Local mode vs cloud mode

If `OCTOPODA_API_KEY` is set, messages go to Octopoda Cloud. If not set, AutoGenMemory falls back to local SQLite at `~/.synrix/data/synrix.db`. Same API, no code change.

Requires octopoda v3.1.4 or newer.

## Common mistakes

**Passing agent_id instead of group_id**

```python
AutoGenMemory(agent_id="x")   # TypeError
```

Use `group_id=`.

**Not filtering event types**

```python
for event in team.run_stream(task="..."):
    memory.store_message(event.source, "group", event.content)
# AttributeError on TaskResult or ToolCallEvent
```

Always check attributes first:

```python
if hasattr(event, 'source') and hasattr(event, 'content'):
    memory.store_message(...)
```

**Forgetting asyncio.run**

```python
async def run(): ...
# script ends without ever running the coroutine
```

The async function must be invoked: `asyncio.run(run())` or `await run()` inside another async context.

**model_client=...**

Literal ellipsis is a placeholder in docs. Real code needs a real client:

```python
from autogen_ext.models.openai import OpenAIChatCompletionClient
model = OpenAIChatCompletionClient(model="gpt-4o-mini")
```

**Changing group_id between runs**

```python
AutoGenMemory(group_id="team_1")          # run 1
AutoGenMemory(group_id="team-1")          # run 2
# Different groups. Run 2 sees empty history.
```

Stable group_id is required for persistence.

## Troubleshooting

### TypeError: got an unexpected keyword argument 'agent_id'

Use `group_id=` instead. AutoGen memory is group-scoped.

### AttributeError: 'TaskResult' has no attribute 'content'

Your stream loop isn't filtering event types. See Common Mistakes.

### openai.AuthenticationError

`OPENAI_API_KEY` is not set. Export it.

### ImportError: cannot import name 'OpenAIChatCompletionClient'

Missing the ext package:

```
pip install "autogen-ext[openai]"
```

### AuthError: api_key is required (Octopoda)

You're on octopoda < 3.1.4. Upgrade:

```
pip install --upgrade octopoda
```

v3.1.4+ falls back to local SQLite when no cloud key is set.

### History empty after many runs

Your `group_id` is changing between runs, or your env var isn't being picked up. Check both.

## Next step

For single-agent chat with LangChain, see LangChain. For crew-based task execution, see CrewAI. For raw memory outside any framework, see Vanilla Python.
