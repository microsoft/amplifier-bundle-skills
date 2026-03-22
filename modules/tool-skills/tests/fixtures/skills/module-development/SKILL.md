---
name: module-development
description: Guide for creating new Amplifier modules including protocol implementation, entry points, mount functions, and testing patterns. Use when creating new modules or understanding module architecture.
version: 1.0.0
license: MIT
metadata:
  category: development
  complexity: medium
---

# Module Development Guide

## Creating a New Module

### Step 1: Choose Protocol

Determine which protocol your module implements:

- **Tool**: Agent capability (filesystem, bash, web, database)
- **Provider**: LLM backend (Anthropic, OpenAI, Ollama)
- **Context**: Conversation state management (simple, persistent)
- **Orchestrator**: Execution loop strategy (basic, streaming, events)
- **Hook**: Lifecycle observer (logging, approval, redaction)

### Step 2: Implement Protocol

```python
from typing import Any
from amplifier_core import ModuleCoordinator, ToolResult

class MyTool:
    """Tool for doing something useful."""

    name = "my-tool"
    description = "Does something useful"

    def __init__(self: "MyTool", config: dict[str, Any]) -> None:
        """Initialize tool with configuration."""
        self.config = config
        self.timeout = config.get("timeout", 30)

    @property
    def input_schema(self: "MyTool") -> dict:
        """Return JSON schema for tool parameters."""
        return {
            "type": "object",
            "properties": {
                "param": {"type": "string", "description": "Parameter description"}
            },
            "required": ["param"]
        }

    async def execute(self: "MyTool", input: dict[str, Any]) -> ToolResult:
        """Execute tool operation."""
        param = input.get("param")
        if not param:
            return ToolResult(
                success=False,
                error={"message": "param is required"}
            )

        # Implementation here
        result = f"Processed: {param}"

        return ToolResult(
            success=True,
            output={"result": result}
        )
```

### Step 3: Create Mount Function

```python
async def mount(coordinator: ModuleCoordinator, config: dict[str, Any] | None = None) -> None:
    """
    Mount the tool module.

    Args:
        coordinator: Module coordinator providing infrastructure
        config: Module configuration from profile

    Returns:
        Optional cleanup function
    """
    config = config or {}
    tool = MyTool(config)
    await coordinator.mount("tools", tool, name=tool.name)
    logger.info("Mounted MyTool")
    return
```

### Step 4: Register Entry Point

```toml
# pyproject.toml
[project]
name = "amplifier-module-tool-mytool"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "amplifier-core",
]

[project.entry-points."amplifier.modules"]
tool-mytool = "amplifier_module_tool_mytool:mount"

[tool.uv.sources]
amplifier-core = { path = "../amplifier-core", editable = true }
```

## Module Structure

**Required files:**

```
amplifier-module-tool-mytool/
├── amplifier_module_tool_mytool/
│   ├── __init__.py              # mount() + tool class
│   └── (optional modules)
├── tests/
│   └── test_mytool.py
├── pyproject.toml
├── Makefile
└── README.md
```

## Using Coordinator Infrastructure

The coordinator provides infrastructure context:

```python
async def mount(coordinator: ModuleCoordinator, config: dict[str, Any] | None = None) -> None:
    # Access infrastructure
    session_id = coordinator.session_id          # Current session
    parent_id = coordinator.parent_id            # Parent session (if child)
    session_config = coordinator.config          # Full session configuration
    loader = coordinator.loader                  # Dynamic module loading

    # Emit events
    await coordinator.hooks.emit("module:mounted", {
        "module_type": "tool",
        "module_name": "my-tool"
    })

    # Register capabilities (optional)
    coordinator.register_capability("my-tool.version", "1.0.0")

    # Register cleanup (optional)
    async def cleanup():
        logger.info("Cleaning up MyTool")
    coordinator.register_cleanup(cleanup)
```

## Testing Modules

**Use TestCoordinator:**

```python
import pytest
from amplifier_core.testing import TestCoordinator
from amplifier_module_tool_mytool import mount

@pytest.mark.asyncio
async def test_tool_execution():
    coordinator = TestCoordinator()

    # Mount module
    await mount(coordinator, {"timeout": 10})

    # Get tool
    tool = coordinator.get("tools", "my-tool")
    assert tool is not None

    # Execute
    result = await tool.execute({"param": "test"})
    assert result.success
    assert "Processed: test" in result.output["result"]
```

## Common Patterns

### Configuration Handling

```python
class MyTool:
    def __init__(self: "MyTool", config: dict[str, Any]) -> None:
        # Required config
        self.required = config.get("required_param")
        if not self.required:
            raise ValueError("required_param must be provided")

        # Optional config with defaults
        self.timeout = config.get("timeout", 30)
        self.retries = config.get("retries", 3)
```

### Event Emission

```python
async def execute(self: "MyTool", input: dict[str, Any]) -> ToolResult:
    # Events emitted by orchestrator via hooks, not by tools directly
    # Tools just return results
    result = await self._process(input)
    return ToolResult(success=True, output=result)
```

### Error Patterns

```python
# Return error, don't raise
return ToolResult(
    success=False,
    error={"message": "Clear error message", "code": "ERROR_CODE"}
)

# Log for debugging
logger.error(f"Failed to process {input}: {e}")
return ToolResult(success=False, error={"message": str(e)})
```

## Remember

- **One responsibility per module** - Don't create mega-modules
- **Config via mount()** - No hard-coded defaults in modules
- **Async everywhere** - All I/O must be async
- **Protocols not inheritance** - Implement interface, don't inherit
- **Test at protocol level** - Test behavior, not internals
