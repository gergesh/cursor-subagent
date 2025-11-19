# cursor-subagent

**A cursor-agent wrapper with added isolated agent configurations support**

cursor-subagent extends `cursor-agent` with the ability to use isolated configurations for different specialized contexts. Use the same cursor-agent you know, but with `-a designer` to load a design-focused configuration, or `-a backend` for API work.

## Why?

When working on complex projects, you often need different AI behaviors for different tasks:

- **Design work** needs focus on UX, accessibility, visual polish
- **Backend work** needs security-first thinking, database design, API patterns
- **Frontend work** needs component architecture, performance, type safety

This is useful for the "expert" pattern, with each agent having specific knowledge, rules and MCP servers - thus reducing context bloat and improving output.

## Prerequisites

- **macOS** (uses `DYLD_INSERT_LIBRARIES`)
- **Cursor** with cursor-agent installed
- **Clang**
- **uv**: `curl -LsSf https://astral.sh/uv/install.sh | sh`

## Installation

First, install the `cursor-subagent` utility:

```bash
uv tool install git+https://github.com/gergesh/cursor-subagent
```

Then add the `cursorrules` on how to use it to your project

```bash
curl -L https://raw.githubusercontent.com/gergesh/cursor-subagent/refs/heads/master/.cursor/rules/cursor-subagent.mdc -o .cursor/rules/cursor-subagent.mdc
```

## Usage
```
# Standard usage
cursor-subagent -a <agent> --approve-mcps -f -p "<prompt>"

# Examples
cursor-subagent -a designer --approve-mcps -f -p "refactor theme system"
cursor-subagent -a backend --approve-mcps  -f -p "add JWT authentication"
cursor-subagent -a frontend --approve-mcps -f -p "add error boundary"

# List available agents
cursor-subagent list-agents
```

## How It Works

When you use `-a <agent>`, cursor-subagent injects a dylib into the normal `cursor-agent` invocation.
It incercepts filesystem calls and redirects all `.cursor/*` file reads to access `.cursor/agents/<agent>/` under the hood instead.
This means cursor-agent transparently loads the agent's `.cursorrules` and `mcp.json` without knowing anything changed.

## Creating Agents

### Directory Structure

Agents live in `.cursor/agents/<name>/`:

```
.cursor/agents/designer/
└── description.txt        # Brief description
├── .cursorrules           # Agent-specific rules
├── rules/                 # Additional rules
├── mcp.json               # Agent-specific MCP servers
```

## MCP Server (Optional)

cursor-subagent additionally implements an MCP server to access its functionality:

### Setup

Add to `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "cursor-subagent": {
      "command": "uvx",
      "args": ["cursor-subagent", "mcp-server"]
    }
  }
}
```

Restart Cursor, and you can ask the AI to use these tools:
- `list-agents` - List available agents
- `spawn-agent` - Run cursor-agent with an agent configuration
- `create-agent` - Create a new agent

## Contributing

Contributions welcome!

- Linux/Windows support
- Bug fixes and improvements
- Documentation enhancements

## Special Thanks

- [Yair Chuchem's system call interception](https://yairchu.github.io/posts/intercept-to-fix)
- [BallisKit's dylib injection research](https://blog.balliskit.com/macos-dylib-injection-at-scale-designing-a-self-sufficient-loader-da8799a56ada)
- [Anysphere's Eric Zakariassonon X](https://x.com/ericzakariasson/status/1958991610798383165)

---

**cursor-subagent is an independent third-party project and not affiliated with Cursor or Anysphere, Inc.**
