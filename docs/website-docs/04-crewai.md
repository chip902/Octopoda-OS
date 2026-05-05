# CrewAI

CrewAIMemory is a crew-scoped memory bus. Persist task outputs after each kickoff and store role-tagged findings that any future run can read.

**Requires:** Python 3.9+, octopoda 3.1.4+, crewai 1.x
**Setup time:** 3 minutes
**Prerequisite:** Finish Getting started so your API key is set.

## Install

```
pip install octopoda crewai
```

Your Crew's LLM also needs its own key in the environment:

```
export OPENAI_API_KEY=sk-...
```

CrewAI supports many LLM backends (OpenAI, Anthropic, Groq, Ollama). Set whichever key matches your chosen model.

## Two-step integration

### Step 1 — Import the memory bus

```python
from octopoda import CrewAIMemory
```

### Step 2 — Attach it to your crew

```python
memory = CrewAIMemory(crew_id="your_crew_id")
```

`crew_id` is one string per crew configuration. Use the same value every time you run the crew, or findings from prior runs won't be visible.

Common patterns:

```python
CrewAIMemory(crew_id="market_research_crew")       # one per crew name
CrewAIMemory(crew_id=f"research_{project_id}")     # one per project
```

## Persist task results after each kickoff

After the crew finishes running, iterate the tasks output and persist each:

```python
result = crew.kickoff()

for i, task_output in enumerate(result.tasks_output):
    memory.store_task_result(
        task_name=f"task_{i+1}",
        result=str(task_output.raw),
        agent_role=str(task_output.agent),
    )
```

### store_task_result signature

```python
memory.store_task_result(task_name, result, agent_role)
```

Three positional arguments in this exact order. Pass them as keywords if you want to be explicit:

```python
memory.store_task_result(
    task_name="market_scan",
    result="Found 3 vector DBs",
    agent_role="researcher",
)
```

## Store long-term findings

Task results are episodic — they record what each task produced in a specific kickoff. For durable knowledge any future kickoff should read, use `store_finding`:

```python
memory.store_finding(
    agent_role="researcher",
    key="top_competitor",
    finding="Pinecone leads in managed vector DBs",
)
```

### store_finding signature

```python
memory.store_finding(agent_role, key, finding)
```

Three positional arguments. The order is DIFFERENT from store_task_result (agent_role comes first here, last there). Easy to mix up.

`finding` can be any JSON-serialisable value: string, dict, list, nested.

## Retrieve findings in later runs

```python
memory = CrewAIMemory(crew_id="your_crew_id")     # same crew_id
findings = memory.get_all_findings()

for f in findings:
    print(f["key"], "->", f["data"]["value"])
```

Each finding is a dict with `key` (what you passed as `key`) and `data` (which contains your original value under `data["value"]` plus metadata tags).

## More memory API

Octopoda provides additional methods for deeper memory management:

```python
# One specific finding
memory.get_finding("top_competitor")

# All findings grouped for a knowledge base view
memory.get_crew_knowledge_base()

# Full crew snapshot (state + findings + task results)
memory.crew_snapshot(label="pre_migration")

# Restore from snapshot
memory.crew_restore(label="pre_migration")
```

## Task results vs findings — when to use which

| You're storing... | Use |
|---|---|
| What each task produced in one specific run | `store_task_result` |
| A fact that future runs should know | `store_finding` |
| A point-in-time checkpoint of everything | `crew_snapshot` |

Rule of thumb: if it's "this run produced X" → task result. If it's "we now know X" → finding.

## Octopoda memory and CrewAI's built-in memory

CrewAI has its own memory system (enabled with `memory=True` on Crew). The two coexist:

- CrewAI's memory is episodic within a kickoff (keeps agents in sync during one run)
- Octopoda memory is persistent across kickoffs (your team's knowledge base)

You can use both. `memory=True` on Crew doesn't interfere with Octopoda. If you only want Octopoda (simpler, no conflicts), leave `memory=False`.

## Full example

```python
import os
os.environ["OPENAI_API_KEY"] = "sk-..."

from crewai import Agent, Task, Crew, Process, LLM
from octopoda import CrewAIMemory

llm = LLM(model="gpt-4o-mini", temperature=0.2)

researcher = Agent(
    role="Market Researcher",
    goal="Find emerging competitors in AI memory tools",
    backstory="You are a concise analyst who outputs short factual statements.",
    llm=llm,
    verbose=False,
)

task = Task(
    description="Name two popular open-source agent memory libraries in 2026.",
    expected_output="Two library names, one per line.",
    agent=researcher,
)

crew = Crew(agents=[researcher], tasks=[task], process=Process.sequential, verbose=False)
memory = CrewAIMemory(crew_id="market_research_crew")

# Print any prior findings the crew already knows
for f in memory.get_all_findings():
    print("Prior finding:", f["key"], "->", f["data"]["value"])

# Run the crew
result = crew.kickoff()

# Persist task results
for i, task_output in enumerate(result.tasks_output):
    memory.store_task_result(
        task_name=f"task_{i+1}",
        result=str(task_output.raw),
        agent_role=str(task_output.agent),
    )

# Store a new finding for future runs
memory.store_finding(
    agent_role="researcher",
    key="top_two_libraries_2026",
    finding=str(result),
)
```

## Common mistakes

**Swapping argument orders between store_finding and store_task_result**

```python
memory.store_finding("task_x", "result", "researcher")
# Wrong — this passes task_x as agent_role
```

Always use keyword args to be safe:

```python
memory.store_finding(agent_role="researcher", key="task_x", finding="result")
```

**Changing crew_id between runs**

```python
# First run
CrewAIMemory(crew_id="research_crew").store_finding(...)

# Second run
CrewAIMemory(crew_id="research-crew").get_all_findings()
# Returns []  — underscore vs hyphen = different crew
```

Stable `crew_id` is the only way findings carry between runs.

**Forgetting Task needs expected_output**

```python
Task(description="...", agent=researcher)
# CrewAI 1.x: ValidationError — expected_output is required
```

Always provide `expected_output` with a short description of what the task should produce.

**Agent has no LLM**

```python
Agent(role="...", goal="...", backstory="...")
# CrewAI: error or silent fallback to default
```

Explicitly pass `llm=LLM(model="gpt-4o-mini")` or equivalent.

## Troubleshooting

### `pydantic.ValidationError: expected_output Field required`

CrewAI 1.x requires `expected_output` on every Task. Add it.

### `openai.AuthenticationError`

`OPENAI_API_KEY` not set. Export it.

### Findings from previous run don't appear

Your `crew_id` changed between runs. Case-sensitive, whitespace matters. Match exactly.

### `store_finding` silently stored with wrong fields

You mixed up argument order. Use keyword args:

```python
memory.store_finding(agent_role=..., key=..., finding=...)
```

### AuthError: api_key is required

You're on octopoda < 3.1.4 in local mode. Upgrade:

```
pip install --upgrade octopoda
```

v3.1.4+ falls back to local SQLite automatically when no cloud key is set.

## Next step

For single-agent persistence without CrewAI, see Vanilla Python. For multi-agent chat without task structure, see AutoGen.
