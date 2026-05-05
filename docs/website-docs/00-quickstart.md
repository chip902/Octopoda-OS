# Quickstart

One pip install gives any AI agent persistent memory plus automatic loop detection, audit trails, and crash recovery. Runs local or cloud.

## What persistent memory actually means

AI agents have no memory between conversations. Close the tab, start a new chat, the agent has forgotten everything. Octopoda fixes that with a single line:

```python
agent.remember("user:name", "Alice")
```

That line runs once. From then on, in any future session, on any machine, you can call:

```python
agent.recall("user:name")  # → "Alice"
```

Your agent's important facts persist forever. You choose what's worth saving.

## What's automatic vs what you call

**Automatic, zero code:** loop detection, audit trail, crash recovery, memory versioning, health monitoring, cost tracking, auto-snapshots. You get all of these in the background the moment you install.

**You call once:** `agent.remember("key", "value")` tells Octopoda what's worth storing. From then on, recall is free and forever.

For LangChain users, even the saves are automatic once wired. For Claude Code / Cursor / Windsurf users via MCP, the AI itself decides when to save.

## Install in 30 seconds

```
pip install octopoda
```

Sign up at octopodas.com/signup, copy your API key, set it:

```
export OCTOPODA_API_KEY=sk-octopoda-...
```

## Your first working code in 3 lines

```python
from octopoda import AgentRuntime

agent = AgentRuntime("my_first_agent")
agent.remember("hello", "world")
print(agent.recall("hello").value)  # → "world"
```

That's a working agent with persistent memory. Close Python, reopen, run the recall again — it still says "world".

## Pick your path

Each framework has a short guide that shows how to plug Octopoda in. Here's what you get with each:

| Framework | What you get | How automatic? |
|---|---|---|
| **Vanilla Python** | Any Python script gets persistent memory with one line per save. Full control. | You call `remember` and `recall` |
| **LangChain** | Your chain auto-saves every conversation turn. Zero extra lines after wiring. | Fully automatic |
| **CrewAI** | Your crew's task outputs and long-term findings persist across kickoffs. | You call `store_task_result` after each kickoff |
| **AutoGen** | Group chat messages persist across process restarts. Replay any conversation. | You call `store_message` in your event loop |
| **OpenAI Assistants** | Thread state survives process restarts. Assistants resume mid-conversation. | You call `store_thread_state` after each run |
| **MCP (Claude Code, Cursor, Windsurf, Codex)** | Your AI editor gets 28 memory tools it can call directly. | Fully automatic — AI decides when to save |

## Cloud or local, same code

If your `OCTOPODA_API_KEY` is set, memories go to Octopoda Cloud. If not, they go to a local SQLite file at `~/.synrix/data/synrix.db`. Same code, no changes.

Start local if you want privacy or offline. Add the env var later to sync to cloud.

## Pick your next page

- Never integrated a memory tool before? → **Getting started** (detailed setup, troubleshooting)
- Plain Python agent? → **Vanilla Python**
- Using LangChain, CrewAI, AutoGen, or OpenAI Assistants? → the matching framework guide
- Want the Claude Code / Cursor experience? → **MCP**

Each guide is 2-3 minutes to follow and ends with your agent remembering things across restarts.
