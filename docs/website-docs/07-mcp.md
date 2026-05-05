# MCP: Claude Code, Cursor, Windsurf, Codex

Give your AI editor 28 memory tools it can call directly. Once configured, the editor remembers context across sessions and projects.

## Quickstart

Install the MCP extras:

```
pip install "octopoda[mcp]"
```

Then configure your editor (pick your product below), restart, done.

**What it does:** adds tools like `octopoda_remember`, `octopoda_recall`, `octopoda_share` to your AI assistant. The assistant decides when to use them. You set up the config once and forget about it.

---

## Configure your editor

### Claude Code (Anthropic's CLI)

In your terminal, run:

```
claude mcp add octopoda python -m synrix_runtime.api.mcp_server -e OCTOPODA_API_KEY=sk-octopoda-paste_your_key_here
```

Replace the placeholder with your real key. The command writes your config for you — no JSON editing needed.

For local-only mode with no cloud account, set the env value to the string `"local"`.

### Claude Desktop (Anthropic's GUI app)

Edit this file (create it if it does not exist):

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

Paste:

```json
{
  "mcpServers": {
    "octopoda": {
      "command": "python",
      "args": ["-m", "synrix_runtime.api.mcp_server"],
      "env": {
        "OCTOPODA_API_KEY": "sk-octopoda-paste_your_key_here"
      }
    }
  }
}
```

### Cursor

Open Settings → Features → MCP → Add server. Or edit `~/.cursor/mcp.json` directly with the same JSON block as above.

### Windsurf

Open Settings → Cascade → MCP. Or edit `~/.codeium/windsurf/mcp_config.json` with the same JSON block.

### Codex (OpenAI's CLI)

Check Codex's current MCP documentation — their config format varies by version.

## Local-only mode

In any of the configs above, set the key to the string `"local"`:

```
"OCTOPODA_API_KEY": "local"
```

Octopoda detects it is not a real key and stores everything locally at `~/.synrix/data/synrix.db`. No cloud account needed.

## Restart your editor

MCP servers only load at startup. Fully quit your editor and reopen it — a reload or refresh will not pick up the change.

## Verify it works

Ask your assistant: "Use the `octopoda_remember` tool to store my name as Alice." It should use the tool and confirm. Then in a new conversation: "Use `octopoda_recall` to get my name." It should return Alice.

## Troubleshooting

If the tool is not available:

- Did you FULLY restart the editor? Not a reload. Quit completely.
- Is `python` on your system PATH? Run `which python` on macOS/Linux or `where python` on Windows. If the result is not a working Python with octopoda installed, replace `"command": "python"` with the absolute path.
- Was the `[mcp]` extra installed? Run `pip install "octopoda[mcp]" --upgrade`.
- Does your JSON file have syntax errors? Validate at jsonlint.com.

On Windows, `python` sometimes launches the Microsoft Store stub. If that happens, use `"py"` as the command instead, or use the full path to your real Python install.
