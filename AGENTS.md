# cursor-subagent Developer Guide

This document is for developers working on the cursor-subagent codebase.

## Architecture Overview

cursor-subagent uses **dylib injection** to transparently redirect filesystem operations. When cursor-agent runs under cursor-subagent, it reads from `.cursor/agents/<name>/` instead of `.cursor/` without any awareness of the redirection.

### Core Components

```
cursor_subagent/
├── __main__.py           # Entry point
├── cli.py               # CLI argument parsing and command dispatch
├── core.py              # Agent execution logic
├── build.py             # Dylib compilation
├── server.py            # MCP server implementation
└── redirect_interpose.c # C library for path interception
```

### How It Works

1. **Dylib Injection**: Sets `DYLD_INSERT_LIBRARIES` to load `libcursor_redirect.dylib`
2. **Path Interception**: C library intercepts `open()`, `stat()`, `access()`, etc.
3. **Path Rewriting**: Converts `.cursor/` → `.cursor/agents/<name>/` transparently
4. **Fallback Logic**: Falls back to `.cursor/` if agent-specific file doesn't exist

**Execution Flow**:

```
cursor-subagent -a designer -f "modernize"
           ↓
   Inject environment:
     DYLD_INSERT_LIBRARIES=libcursor_redirect.dylib
     CURSOR_REDIRECT_TARGET=.cursor/agents/designer/
           ↓
   Forward to cursor-agent: -f "modernize"
           ↓
   cursor-agent reads .cursor/.cursorrules
           ↓
   Dylib redirects to .cursor/agents/designer/.cursorrules
           ↓
   cursor-agent loads designer's rules ✓
```

## Prerequisites

Before developing cursor-subagent, ensure you have:

- **macOS** (currently the only supported platform)
- **Xcode Command Line Tools**: `xcode-select --install`
- **Python 3.8+**
- **uv** (recommended): `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **cursor-agent** installed (via Cursor IDE)
- **gcc/clang** compiler (comes with Xcode Command Line Tools)

## Development Setup

```bash
# Clone the repo
git clone https://github.com/yourusername/cursor-subagent.git
cd cursor-subagent

# Install in development mode (using uv)
uv sync

# Or use pip
pip install -e .

# Build the dylib
python -m cursor_subagent.build

# Or use the build script
./build.sh

# Run tests
python -m pytest tests/
```

## Key Files Explained

### `redirect_interpose.c`

The heart of the system. This C library uses `DYLD_INTERPOSE` to intercept POSIX filesystem calls:

- `open()`, `openat()`
- `stat()`, `lstat()`, `fstatat()`
- `access()`, `faccessat()`
- `readlink()`, `readlinkat()`
- `realpath()`

**Key function**: `redirect_path()` performs the actual path rewriting:

```c
char* redirect_path(const char* path) {
    // If path contains ".cursor/" and not ".cursor/agents/"
    // Rewrite to ".cursor/agents/<TARGET>/"
    // Fall back to original if redirected path doesn't exist
}
```

**Environment variables**:
- `CURSOR_REDIRECT_TARGET`: The agent name (e.g., "backend")
- `CURSOR_REDIRECT_DEBUG`: Enable debug logging

### `core.py`

Contains the main execution logic:

- `run_cursor_agent()`: Sets up environment, injects dylib, executes cursor-agent
- `find_cursor_agent()`: Locates cursor-agent binary
- `list_agents()`: Discovers available agents in workspace

**Key logic**:

```python
def run_cursor_agent(agent_name=None, ...):
    if agent_name:
        # Set up dylib injection
        env["DYLD_INSERT_LIBRARIES"] = dylib_path
        env["CURSOR_REDIRECT_TARGET"] = agent_name

    # Execute cursor-agent with modified environment
    subprocess.run([cursor_agent_path] + args, env=env)
```

### `cli.py`

Handles CLI parsing and command routing:

- `main()`: Entry point for CLI
- Argument parsing with `argparse`
- Command dispatch (`--check`, `--build`, `mcp`, etc.)

**Special handling**:
- `list-agents` command
- `--agent/-a` flag for agent selection
- MCP server mode

### `build.py`

Compiles the C dylib:

```python
def build_dylib():
    gcc_cmd = [
        "gcc",
        "-dynamiclib",
        "-o", output_path,
        source_path,
        "-Wall", "-Wextra"
    ]
    subprocess.run(gcc_cmd, check=True)
```

**Installation locations**:
1. Project directory: `cursor_subagent/libcursor_redirect.dylib`
2. User installation: `~/.local/share/cursor_subagent/libcursor_redirect.dylib`

### `server.py`

MCP (Model Context Protocol) server implementation for integration with Cursor's AI:

- `SubagentServer`: MCP server class
- `run_subagent()`: Tool for executing agents from AI chat
- `list_available_agents()`: Tool for discovering agents

## Building and Packaging

### Local Build

```bash
# Build dylib only
python -m cursor_subagent.build

# Build and install package locally
pip install -e .

# Run from source
python -m cursor_subagent --check
```

### Distribution Build

```bash
# Build wheel with dylib included
python setup.py bdist_wheel

# Build source distribution
python setup.py sdist

# Upload to PyPI
python -m twine upload dist/*
```

**Important**: `MANIFEST.in` must include:

```
include cursor_subagent/redirect_interpose.c
include cursor_subagent/libcursor_redirect.dylib
```

## Testing

### Manual Testing

```bash
# Test dylib compilation
cursor-subagent --check

# Test agent execution
mkdir -p .cursor/agents/test
echo "Test rules" > .cursor/agents/test/.cursorrules
cursor-subagent -a test -f "echo test"

# Test with debug logging
export CURSOR_REDIRECT_DEBUG=1
cursor-subagent -a test -f "echo test"
```

### Automated Tests

```bash
# Run test suite
python -m pytest tests/

# Run with coverage
python -m pytest --cov=cursor_subagent tests/
```

**Test categories**:
- Unit tests for path redirection logic
- Integration tests for agent execution
- MCP server tests

## Debugging

### Enable Debug Logging

```bash
export CURSOR_REDIRECT_DEBUG=1
cursor-subagent -a backend -f "test"
```

This logs all path interceptions to stderr:

```
[CURSOR_REDIRECT] Intercepted: .cursor/mcp.json
[CURSOR_REDIRECT] Redirected to: .cursor/agents/backend/mcp.json
[CURSOR_REDIRECT] File exists, using redirected path
```

### Common Issues

**Dylib not loading**:
```bash
# Check if dylib exists
ls ~/.local/share/cursor_subagent/libcursor_redirect.dylib

# Rebuild
cursor-subagent --build

# Verify with otool
otool -L ~/.local/share/cursor_subagent/libcursor_redirect.dylib
```

**SIP (System Integrity Protection) blocking injection**:
- Dylib injection doesn't work on system binaries
- cursor-agent must be in a user-writable location
- Test with: `csrutil status`

**Path redirection not working**:
```bash
# Test the dylib manually
export DYLD_INSERT_LIBRARIES="$HOME/.local/share/cursor_subagent/libcursor_redirect.dylib"
export CURSOR_REDIRECT_SOURCE=".cursor"
export CURSOR_REDIRECT_TARGET=".cursor/agents/designer"
export CURSOR_REDIRECT_DEBUG=1

# Now cursor-agent will use designer's config
cursor-agent -f "test prompt"
```

## Platform Support

### Current: macOS Only

Uses macOS-specific features:
- `DYLD_INSERT_LIBRARIES` (macOS dylib injection)
- `DYLD_INTERPOSE` (macOS function interposition)

### Future: Linux Support

Would require:
- `LD_PRELOAD` instead of `DYLD_INSERT_LIBRARIES`
- Different interposition mechanism (function wrapping)
- Shared object (`.so`) instead of dylib (`.dylib`)

### Not Planned: Windows Support

Windows doesn't have equivalent lightweight injection:
- Would need DLL injection (complex)
- Or kernel-level filesystem filter (overkill)
- Or patching cursor-agent binary (fragile)

## Current Limitations

- **macOS only**: Uses `DYLD_INSERT_LIBRARIES` which is macOS-specific
- **No shared context between agents**: Each agent execution is isolated
- **Requires cursor-agent**: Must have Cursor IDE installed with cursor-agent available
- **SIP restrictions**: May not work with system-protected binaries
- **No agent inheritance**: Agents can't extend/inherit from base agents yet

## Release Process

### Version Bumping

Update version in:
1. `pyproject.toml`
2. `setup.py`
3. `cursor_subagent/__init__.py`

### Pre-Release Checklist

- [ ] All tests pass
- [ ] Dylib compiles cleanly
- [ ] Manual testing on clean macOS install
- [ ] Documentation updated
- [ ] CHANGELOG.md updated

### Publishing

```bash
# Clean previous builds
rm -rf dist/ build/ *.egg-info

# Build distributions
python setup.py sdist bdist_wheel

# Check package
twine check dist/*

# Upload to PyPI
twine upload dist/*

# Tag release
git tag v0.x.0
git push origin v0.x.0
```

## Code Style

- Python: Follow PEP 8
- C: Follow Linux kernel style (tabs, K&R braces)
- Use type hints in Python code
- Document public APIs

## Contributing

### Adding New Features

1. **New CLI command**: Add to `cli.py`, implement in appropriate module
2. **New interposition**: Add to `redirect_interpose.c`, test thoroughly
3. **MCP tool**: Add to `server.py`, follow MCP protocol

### Pull Request Guidelines

- Include tests for new functionality
- Update documentation
- Ensure `--check` passes
- Test on clean macOS system

## Architecture Decisions

### Why Dylib Injection?

**Alternatives considered**:
1. **Wrapper script**: Would require cursor-agent to accept config path
2. **Symbolic links**: Too fragile, breaks with absolute paths
3. **FUSE filesystem**: Overkill, requires kernel extension on macOS
4. **Patch cursor-agent**: Fragile, breaks with updates

**Dylib injection wins**: Transparent, robust, no cursor-agent changes needed

### Why C for Redirection?

- POSIX calls are C APIs
- Python can't intercept another process's system calls
- Dylib must be native code for `DYLD_INTERPOSE`

### Why Not LD_PRELOAD Initially?

- Started as macOS-only tool
- `DYLD_INTERPOSE` is cleaner than `LD_PRELOAD` symbol wrapping
- Linux support is planned but not yet prioritized

## Future Enhancements

### Short Term
- [ ] Linux support (LD_PRELOAD)
- [ ] Agent templates (`cursor-subagent init <type>`)
- [ ] Agent validation (`cursor-subagent validate`)
- [ ] Better error messages

### Long Term
- [ ] Agent marketplace/sharing
- [ ] Cloud-synced agent configs
- [ ] Agent composition (inherit from base agent)
- [ ] Performance profiling for agents

## Resources

- [DYLD_INTERPOSE documentation](https://opensource.apple.com/source/dyld/dyld-210.2.3/include/mach-o/dyld-interposing.h)
- [MCP Protocol](https://github.com/anthropics/mcp)
- [Python packaging guide](https://packaging.python.org/)

## Contact

- Issues: GitHub Issues
- Discussions: GitHub Discussions
- Security: security@example.com

## Credits and Prior Art

cursor-subagent builds on excellent research and techniques from the community:

- **[Yair Chuchem's system call interception](https://yairchu.github.io/posts/intercept-to-fix)** - Foundational techniques for POSIX call interception
- **[BallisKit's dylib injection research](https://blog.balliskit.com/macos-dylib-injection-at-scale-designing-a-self-sufficient-loader-da8799a56ada)** - Comprehensive guide to dylib injection on macOS at scale
- **[Eric Zakariasson (Anysphere) on X](https://x.com/ericzakariasson/status/1958991610798383165)** - Original inspiration and cursor-agent insights

---

**cursor-subagent is an independent third-party project and not affiliated with Cursor or Anysphere, Inc.**
