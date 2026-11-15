# Rosh MCP Server

<!-- mcp-name: io.github.rosh-studio/rosh-mcp -->

Let an AI agent build live 3D rooms in [Rosh](https://rosh.cloud) without
rendering anything, and compile and publish Rosh programs.

**Rooms (new in 0.2.0).** A room is a live 3D space on rosh.cloud. The agent
writes Rosh lines; the room checks each one and confirms or refuses it with a
reason; `rosh_room_look` reads the room back as text, with layout notes (things
that overlap, things hidden behind others from where visitors stand, things
underground). The agent never needs a screen. The same room is drawn live by
the browser, and by the Unity and Unreal clients.

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

Go to [rosh.cloud/account/keys](https://rosh.cloud/account/keys) (sign in first),
choose **For an AI agent (MCP)** and **Make key**. The page shows the key once,
with the `claude mcp add` command and the JSON above already filled in.

`rosh_room_guide` needs no key, and `rosh_room_look` works without one on public
rooms; everything else needs `ROSH_API_KEY`.

## Tools

### Rooms

| Tool | Description | Auth Required |
|------|-------------|---------------|
| `rosh_room_guide` | The lines a room understands, with examples: read first | No |
| `rosh_create_room` | Create a room from starting Rosh code | Yes (write) |
| `rosh_list_rooms` | List your rooms | Yes (read) |
| `rosh_room_do` | Send Rosh lines to a live room; each confirmed or refused | Yes (world) |
| `rosh_room_look` | Read a room as text, with layout notes | No (public rooms) |
| `rosh_set_room_code` | Replace a room's starting code | Yes (write) |

A first brief to try: *"Build a small 3D room about Pictish stones for a school
group of 10-year-olds at slug pictish-stones. You cannot see it: check it with
rosh_room_look and fix its layout notes."*

Limits: 20 new rooms an hour per key by default; rooms can't be deleted through
the API yet.

### Programs

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
