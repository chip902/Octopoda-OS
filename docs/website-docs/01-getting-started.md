# Getting Started

You'll install the SDK, sign up for a free key, set it in your environment, and run a five-line sanity check to confirm everything works. After that, jump to your framework guide.

This takes about five minutes. No credit card, no usage limits during setup.

## Before you start

You need:

- A computer running macOS, Linux, or Windows 10+
- Python 3.9 or newer already installed (we show you how to check below)
- A terminal (Terminal on Mac, Terminal on Linux, PowerShell or Command Prompt on Windows)

You do NOT need:

- An existing AI agent. The Vanilla Python guide is a complete standalone starter — skip there if you're new.
- A credit card. The free tier covers 5 agents, 5,000 memories, and 100 free AI extractions.
- A cloud account. Local mode works with no signup at all.

## Step 1. Check your Python version

In your terminal, run:

```
python --version
```

You should see something like:

```
Python 3.12.5
```

Any version starting with 3.9, 3.10, 3.11, 3.12, or 3.13 works.

### Why 3.9 or newer?

Octopoda uses type hints and async features that were added in Python 3.9. Older versions (3.8, 3.7) will fail to import the SDK with cryptic syntax errors. This is a hard requirement.

### If you see an older version

You have two Python installs coexisting. Try:

```
python3 --version
```

If that shows 3.9 or newer, use `python3` and `pip3` everywhere this guide says `python` and `pip`. They're the same tools, just named to pick the newer interpreter.

If neither shows 3.9+, install from python.org/downloads. On macOS, `brew install python@3.12` also works if you use Homebrew.

### If you see "python: command not found"

Python isn't installed, or it's installed but not on your PATH. On Windows, running `python` sometimes opens the Microsoft Store — that's the Windows Python stub, not a real install. Use:

```
py --version
```

If that works, use `py` and `py -m pip` everywhere this guide uses `python` and `pip`.

## Step 2. Check pip works

`pip` is Python's package installer. It came bundled with Python in your previous step. Verify it's available:

```
pip --version
```

You should see:

```
pip 24.0 from /usr/lib/python3.12/site-packages/pip (python 3.12)
```

The numbers don't matter — any version works. The point is that pip is found and reports which Python it belongs to.

### If pip is missing

Rare but fixable:

```
python -m ensurepip --upgrade
```

Then retry `pip --version`.

## Step 3. Sign up and get your API key

Go to octopodas.com/signup.

Fill in first name, last name, email, password. Click Create account.

### Verify your email

We send a six-digit verification code to your email within 30 seconds. The code is valid for 15 minutes.

If it hasn't arrived after 90 seconds:

- Check your spam or junk folder
- Check if you have email rules auto-filing anything from `noreply@octopodas.com`
- Use the "Resend code" button on the verification screen

After entering the code, you land on the dashboard.

### Copy your API key

Your API key is visible on the dashboard. It looks like:

```
sk-octopoda-1aB2cD3eF4gH5iJ6kL7mN8oP9qR0sT
```

Always starts with `sk-octopoda-`. Always 53 characters total.

Copy it. You'll use it in the next step.

### Keep your key safe

This key authenticates your account to Octopoda. Treat it like a password:

- Do not commit it to git (use environment variables, as we do in Step 4)
- Do not paste it into public chat, Slack, or GitHub issues
- Do not share it with colleagues (generate separate keys for each person from Dashboard → Settings → API Keys)

If a key leaks, go to Dashboard → Settings → API Keys and click Revoke. Generate a new one. Update your environments. No other cleanup needed.

### Can I always see the key later?

Yes. Go to Dashboard → Settings → API Keys any time. You can also generate additional keys for different projects or team members.

## Step 4. Set your API key as an environment variable

An environment variable is a setting your terminal and any program you run from it can read. The Octopoda SDK looks for `OCTOPODA_API_KEY` automatically — you don't need to pass it in code.

Pick the section that matches your operating system.

### macOS and Linux (bash, zsh)

In your terminal, replace the placeholder with your real key:

```
export OCTOPODA_API_KEY=sk-octopoda-paste_your_key_here
```

Verify it's set:

```
echo $OCTOPODA_API_KEY
```

Your key should print back. If you see a blank line, the export didn't work — try again.

#### Make it permanent

The export above only lasts until you close your terminal. To persist across restarts, add the line to your shell config file.

First, check which shell you're on:

```
echo $SHELL
```

On modern macOS (zsh):

```
echo 'export OCTOPODA_API_KEY=sk-octopoda-paste_your_key_here' >> ~/.zshrc
source ~/.zshrc
```

On most Linux or older macOS (bash):

```
echo 'export OCTOPODA_API_KEY=sk-octopoda-paste_your_key_here' >> ~/.bashrc
source ~/.bashrc
```

If `~/.zshrc` or `~/.bashrc` doesn't exist, use `~/.bash_profile` instead (common on older macOS).

On Fish shell:

```
set -Ux OCTOPODA_API_KEY sk-octopoda-paste_your_key_here
```

(Fish sets persistent vars in one command. No file edit needed.)

### Windows PowerShell

```
$env:OCTOPODA_API_KEY="sk-octopoda-paste_your_key_here"
```

Verify:

```
echo $env:OCTOPODA_API_KEY
```

#### Make it permanent on Windows

The `$env:` command above only works in the current PowerShell window. To persist:

1. Press the Windows key
2. Type environment variables
3. Click Edit the system environment variables
4. In the dialog, click Environment Variables
5. Under User variables, click New
6. Variable name: OCTOPODA_API_KEY
7. Variable value: your key
8. Click OK on all three dialogs
9. Close and reopen your terminal — the new variable is now available

### Windows Command Prompt

For the current window only:

```
set OCTOPODA_API_KEY=sk-octopoda-paste_your_key_here
```

Verify with:

```
echo %OCTOPODA_API_KEY%
```

To persist permanently from CMD, use `setx`:

```
setx OCTOPODA_API_KEY "sk-octopoda-paste_your_key_here"
```

After running `setx`, close and reopen CMD for the change to take effect.

### Inside your Python script

This is the OS-independent fallback. It works anywhere Python runs:

```python
import os
os.environ['OCTOPODA_API_KEY'] = 'sk-octopoda-paste_your_key_here'

from octopoda import AgentRuntime
```

This only sets the key for that specific script. Useful in CI, Docker containers, or when you don't want to touch shell config.

### Verify in a fresh terminal

A common mistake: set the variable, then open a new terminal and forget it's only in the old one.

After setting permanently, open a completely new terminal window and run the echo command for your OS. Your key should print. If not, the permanent step didn't take — redo it.

### Check for hidden whitespace

If your sanity check later fails with AuthError even though you pasted the key correctly, you may have hidden whitespace at the end. Check:

```
echo -n "$OCTOPODA_API_KEY" | wc -c
```

This should print 53. If it prints 54 or higher, reset the variable and paste carefully — your email client or browser may have added a trailing newline or space.

## Step 5. Install the SDK

In your terminal:

```
pip install octopoda
```

This downloads the core package and a few small dependencies (requests and pydantic). It takes 30 seconds to 2 minutes depending on your internet speed.

When finished, the last line prints:

```
Successfully installed octopoda-3.1.4 ...
```

Verify the install landed:

```
python -c "import octopoda; print(octopoda.__version__)"
```

You should see:

```
3.1.4
```

Or any higher version.

### Optional extras (install later, as needed)

The core install covers 90% of use cases. Install these extras only if you need them:

```
pip install "octopoda[mcp]"     # MCP server for Claude Code, Cursor
pip install "octopoda[ai]"      # Semantic search (sentence-transformers)
pip install "octopoda[nlp]"     # Knowledge graph (spaCy)
pip install "octopoda[server]"  # Self-host the cloud API
pip install "octopoda[all]"     # Everything above
```

The quotes are required on macOS and Linux shells. On Windows CMD they're optional but harmless.

Each extra adds dependencies:
- `[mcp]` adds ~5MB
- `[ai]` adds ~1GB (sentence-transformers + torch)
- `[nlp]` adds ~500MB (spaCy + language models)
- `[server]` adds FastAPI and related

### If pip hangs or times out

Network or firewall issue. Common fixes:

```
pip install --no-cache-dir octopoda       # skip any broken cache
pip install -v octopoda                   # verbose output to see what's stuck
```

If you're behind a corporate proxy, set `HTTPS_PROXY`:

```
export HTTPS_PROXY=http://your-proxy:port
```

### If you see "ModuleNotFoundError" after install

pip installed to a different Python than you're running. Force pip to use the right one:

```
python -m pip install octopoda
```

Then retry the verification command.

### Windows: "Microsoft Visual C++ 14.0 is required"

Some dependencies need C++ build tools. Install them:

1. Go to visualstudio.microsoft.com/visual-cpp-build-tools
2. Download and run the installer
3. In the installer, select Desktop development with C++
4. Complete the install, restart your terminal
5. Retry `pip install octopoda`

## Step 6. Run the sanity check

Before moving to a framework-specific guide, confirm your install, key, and environment are all working together.

Create a file called `sanity.py` with these five lines:

```python
from octopoda import AgentRuntime

agent = AgentRuntime("sanity_check")
agent.remember("hello", "world")
print(agent.recall("hello").value)
```

Run it:

```
python sanity.py
```

Expected output:

```
world
```

That's it. If you see `world`, the SDK works, your key is valid, and the connection to Octopoda Cloud is live.

### What you just proved

- Python can import the Octopoda SDK
- Your environment variable is being read
- Your API key is valid
- Your network can reach api.octopodas.com
- Cloud storage round-trips successfully

You're ready to wire Octopoda into your real agent.

### If you see an error instead

**"AuthError: api_key is required"**
→ Your environment variable isn't set or isn't being read. Run `echo $OCTOPODA_API_KEY` (Mac/Linux) or `echo $env:OCTOPODA_API_KEY` (PowerShell). If it's blank, go back to Step 4.

**"ConnectionError" or long hang**
→ Your network is blocking api.octopodas.com. Test directly:

```
curl -I https://api.octopodas.com/health
```

Expected: `HTTP/1.1 200 OK`.

- "Could not resolve host" → DNS issue, try a different network or DNS server
- Hangs without response → firewall blocking HTTPS. On corporate networks, ask IT to allowlist `*.octopodas.com`
- Returns 200 OK → the problem is in your Python environment. Re-check the env var and key.

**"ModuleNotFoundError: No module named 'octopoda'"**
→ pip installed to a different Python. Run `python -m pip install octopoda`.

**Anything else**
→ Copy the full error message and email joe@octopodas.com with your OS, Python version, and the error. We reply within 24 hours.

## Step 7. Jump to your framework guide

Pick from the sidebar:

- **Vanilla Python** — start here if you don't have a framework
- **LangChain** — for LangChain 1.x chains and agents
- **CrewAI** — for multi-agent crews
- **AutoGen** — for group chats built with autogen-agentchat
- **OpenAI Assistants** — for agents using OpenAI's Assistants API
- **MCP** — for Claude Code, Cursor, Windsurf, Codex integrations
- **OpenClaw** — for OpenClaw Node.js agents

Each guide takes 2-3 minutes to follow. Your sanity check already proved the foundation works — framework integrations only add the specific wiring for your framework.
