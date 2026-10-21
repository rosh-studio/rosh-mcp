# Rosh MCP Server

<!-- mcp-name: io.github.rosh-studio/rosh-mcp -->

Give any AI the power to create and publish interactive web apps, games, and 3D scenes using [Rosh](https://rosh.cloud) — a plain-English programming language.

## What is Rosh?

Rosh lets you write programs in plain English:

```
create box called player at 400 300
set player color "blue"
on key "ArrowRight" then set player x to player x + 5
```

This compiles to a runnable HTML5 canvas app, a Phaser game, or a Three.js 3D scene — depending on the target.

## Quick Start

### Claude Desktop / Claude Code

Add to your MCP config (`~/.claude/mcp.json` or Claude Desktop settings):

```json
{
  "mcpServers": {
    "rosh": {
      "command": "uvx",
      "args": ["rosh-mcp"],
      "env": {
        "ROSH_API_KEY": "rosh_k1_your_key_here"
      }
    }
  }
}
```

### Cursor / Windsurf

Same config format — add to your MCP settings file.

### Get an API Key

1. Create an account at [rosh.cloud](https://rosh.cloud)
2. Go to Settings → API Keys
3. Create a key with `read,write` scopes

> **Note:** All tools require an API key — set `ROSH_API_KEY` before starting the server.

## Tools

| Tool | Description | Auth Required |
|------|-------------|---------------|
| `rosh_docs` | Get the full Rosh language reference | Yes (read) |
| `rosh_compile` | Compile Rosh code to HTML | Yes (read) |
| `rosh_publish` | Publish a program to rosh.cloud | Yes (write) |
| `rosh_list_programs` | List your programs | Yes (read) |
| `rosh_get_program` | Get program details by ID | Yes (read) |
| `rosh_update_program` | Update an existing program | Yes (write) |
| `rosh_delete_program` | Delete a program | Yes (write) |
| `rosh_hide_program` | Hide a program (moderation) | Yes (moderate) |
| `rosh_show_program` | Unhide a program | Yes (moderate) |

## Example Prompts

Try these with any MCP-capable AI:

- **"Build me a space shooter game"** — AI reads docs, writes Rosh code, compiles to Phaser
- **"Create a 3D rotating sculpture"** — compiles to Three.js
- **"Make an interactive dashboard with buttons and counters"** — compiles to web
- **"Show me what Rosh can do"** — AI calls `rosh_docs` and explores

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ROSH_API_KEY` | Yes | — | Your rosh.cloud API key |
| `ROSH_API_BASE` | No | `https://rosh.cloud` | API base URL |

## Development

```bash
git clone https://github.com/rosh-studio/rosh-mcp.git
cd rosh-mcp
pip install -e .
rosh-mcp  # runs the stdio server
```

## License

MIT
