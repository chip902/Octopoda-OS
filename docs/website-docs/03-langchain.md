# LangChain

OctopodaChatHistory plugs into RunnableWithMessageHistory. Your chain keeps the same shape — only the message history backend changes. Works with cloud or local mode from v3.1.4 onward.

**Requires:** Python 3.9+, octopoda 3.1.4+, langchain 1.x
**Setup time:** 3 minutes
**Prerequisite:** Finish Getting started so your API key is set. Local mode (no key) also works from v3.1.4.

## Install

Check your LangChain version:

```
pip show langchain
```

If it's 0.x, upgrade:

```
pip install --upgrade langchain langchain-core
```

Install all the pieces the examples below use:

```
pip install octopoda langchain langchain-core langchain-openai
```

You only need `langchain-openai` if you're using OpenAI as the LLM. For Anthropic: `pip install langchain-anthropic`. For Groq, Ollama, etc., install the matching package.

## Set your LLM key

Octopoda has its own key (`OCTOPODA_API_KEY`, set in Getting started). The LLM also has its own key, which LangChain reads:

```
export OPENAI_API_KEY=sk-...           # for ChatOpenAI
export ANTHROPIC_API_KEY=sk-ant-...    # for ChatAnthropic
```

Both keys must be set for the full example below to run. If only OCTOPODA_API_KEY is set, you'll get `openai.AuthenticationError`.

## Two-step integration

### Step 1 — Import the message history class

```python
from octopoda import OctopodaChatHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
```

`OctopodaChatHistory` is a `BaseChatMessageHistory` subclass. Any LangChain component that accepts a message history accepts this.

### Step 2 — Wrap your chain

Build your chain as normal, then wrap it:

```python
def get_session_history(session_id: str):
    return OctopodaChatHistory(agent_id="your_bot_id", session_id=session_id)

chain_with_memory = RunnableWithMessageHistory(
    your_chain,
    get_session_history,
    input_messages_key="input",
    history_messages_key="history",
)
```

### What `agent_id` and `session_id` mean

- `agent_id` — identifies your bot. One per product or role. Hardcode it.
- `session_id` — identifies a single conversation. Pass a different value per user or per thread.

Example mapping:

```python
# support bot with many users
OctopodaChatHistory(agent_id="support_bot", session_id=f"user_{user_id}")

# research bot with many threads
OctopodaChatHistory(agent_id="research_bot", session_id=f"thread_{thread_id}")
```

## Your prompt template must include MessagesPlaceholder

This is the most common silent failure. If your prompt doesn't inject the history back in, the bot stores memory but acts as if it has none.

```python
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant."),
    MessagesPlaceholder("history"),
    ("human", "{input}"),
])
```

The `history` name in `MessagesPlaceholder` must match the `history_messages_key` you pass to `RunnableWithMessageHistory`.

## Invoke the wrapped chain

```python
config = {"configurable": {"session_id": "user_12345"}}
response = chain_with_memory.invoke({"input": "Hi, I'm Alex."}, config=config)
print(response.content)

response = chain_with_memory.invoke({"input": "What's my name?"}, config=config)
print(response.content)
# "Your name is Alex."
```

Same `session_id` across invocations continues the same conversation. Different `session_id` starts a fresh one.

## Clearing a session's history

To let a user start over without affecting other sessions:

```python
history = OctopodaChatHistory(agent_id="your_bot_id", session_id="user_12345")
history.clear()
```

This deletes only that session's messages. Other sessions under the same `agent_id` are untouched.

## Inspecting raw history

For debugging or custom summarisation:

```python
history = OctopodaChatHistory(agent_id="your_bot_id", session_id="user_12345")
for msg in history.messages:
    print(type(msg).__name__, msg.content)
# HumanMessage Hi, I'm Alex.
# AIMessage Hi Alex, nice to meet you.
```

`.messages` returns a `List[BaseMessage]` — `HumanMessage`, `AIMessage`, `SystemMessage`. Standard LangChain types.

## Async and streaming

Works out of the box with LangChain's async methods:

```python
# async invoke
response = await chain_with_memory.ainvoke({"input": "Hi"}, config=config)

# streaming
async for chunk in chain_with_memory.astream({"input": "Hi"}, config=config):
    print(chunk.content, end="")
```

OctopodaChatHistory saves messages after the invocation completes, regardless of whether you used invoke, ainvoke, stream, or astream.

## LangGraph compatibility

LangGraph users can use OctopodaChatHistory inside a stateful graph by treating it as the conversation memory store for a node. The integration pattern is the same — wrap the runnable node in `RunnableWithMessageHistory` or call the history API directly from within your graph's state updater.

## Local mode vs cloud mode

If `OCTOPODA_API_KEY` is set, messages go to Octopoda Cloud. If not set, OctopodaChatHistory falls back to local SQLite at `~/.synrix/data/synrix.db`. Same API, no code change.

Requires octopoda v3.1.4 or newer. Earlier versions required a cloud key and would raise `AuthError` in local mode.

## Cross-process persistence (the real test)

Two separate files to prove memory survives restarts.

**session_1.py:**

```python
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from octopoda import OctopodaChatHistory

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are helpful. Remember what the user tells you."),
    MessagesPlaceholder("history"),
    ("human", "{input}"),
])
chain = prompt | ChatOpenAI(model="gpt-4o-mini")

def get_history(session_id):
    return OctopodaChatHistory(agent_id="demo_bot", session_id=session_id)

bot = RunnableWithMessageHistory(chain, get_history,
    input_messages_key="input", history_messages_key="history")

cfg = {"configurable": {"session_id": "alice"}}
print(bot.invoke({"input": "My name is Alex. I live in Paris."}, config=cfg).content)
```

**session_2.py** (run AFTER session_1.py exits):

```python
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from octopoda import OctopodaChatHistory

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are helpful. Remember what the user tells you."),
    MessagesPlaceholder("history"),
    ("human", "{input}"),
])
chain = prompt | ChatOpenAI(model="gpt-4o-mini")

def get_history(session_id):
    return OctopodaChatHistory(agent_id="demo_bot", session_id=session_id)

bot = RunnableWithMessageHistory(chain, get_history,
    input_messages_key="input", history_messages_key="history")

cfg = {"configurable": {"session_id": "alice"}}
print(bot.invoke({"input": "What's my name and where do I live?"}, config=cfg).content)
# "Your name is Alex and you live in Paris."
```

If session 2 remembers Alex and Paris, your persistence is working.

## Full example (single file, two turns)

```python
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from octopoda import OctopodaChatHistory

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant."),
    MessagesPlaceholder("history"),
    ("human", "{input}"),
])

chain = prompt | ChatOpenAI(model="gpt-4o-mini")

def get_session_history(session_id: str):
    return OctopodaChatHistory(agent_id="support_bot", session_id=session_id)

bot = RunnableWithMessageHistory(
    chain, get_session_history,
    input_messages_key="input",
    history_messages_key="history",
)

config = {"configurable": {"session_id": "user_12345"}}
print(bot.invoke({"input": "My name is Alex."}, config=config).content)
print(bot.invoke({"input": "What is my name?"}, config=config).content)
```

## Common mistakes

**Forgetting MessagesPlaceholder**

```python
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are helpful."),
    ("human", "{input}"),  # no history injected
])
```

Memory stores correctly but never reaches the LLM. Bot seems amnesiac.

**Mismatched history key name**

```python
prompt = ChatPromptTemplate.from_messages([..., MessagesPlaceholder("chat_history"), ...])

RunnableWithMessageHistory(..., history_messages_key="history")  # different
```

Memory loads but into the wrong slot. Add the wrong name to either side and history disappears.

**Using the deprecated LangChainMemory class**

```python
from octopoda import LangChainMemory  # old, broken on LangChain 1.x
```

Raises `AttributeError: 'SynrixMemory' object has no attribute 'messages'` when wrapped in RunnableWithMessageHistory. Use `OctopodaChatHistory` instead (shown throughout this guide).

**Context window growing forever**

By default, every turn is appended. A 100-turn conversation is sent to the LLM in full every invoke. Either:

- Limit how many messages get injected using LangChain's `trim_messages`
- Periodically `history.clear()` to reset
- Move older messages to semantic memory (via `agent.remember` from the Vanilla Python SDK) and only keep the last N in chat history

## Troubleshooting

### AttributeError: 'SynrixMemory' object has no attribute 'messages'

You're using the deprecated `LangChainMemory`. Switch to `OctopodaChatHistory`:

```
pip install --upgrade octopoda
```

Then in your code:

```python
from octopoda import OctopodaChatHistory
```

### openai.AuthenticationError

`OPENAI_API_KEY` is not set. Run `echo $OPENAI_API_KEY` (or `$env:OPENAI_API_KEY` on Windows). If empty, set it.

### Bot seems to have no memory even though writes succeed

Almost always the prompt template is missing `MessagesPlaceholder("history")`, or the name doesn't match `history_messages_key`. See Common mistakes.

### Memory works in one terminal but not another

Different `OCTOPODA_API_KEY` (or no key in the second terminal, so it falls to local mode — different data location). Check `echo $OCTOPODA_API_KEY` in both windows.

### Invocations get very slow after many turns

Context window is growing. See the last Common Mistake for mitigation.

### AuthError: api_key is required

You're on octopoda < 3.1.4 running in local mode. Upgrade:

```
pip install --upgrade octopoda
```

From v3.1.4 onward, no key = local SQLite fallback. No AuthError.

## Next step

If you're using other LangChain patterns (tools, agents, LangGraph), the same OctopodaChatHistory pattern plugs into any chain-like or graph-like runnable. For multi-agent crews, see the CrewAI guide. For raw memory operations outside a chain, see the Vanilla Python guide.
