---
name: python-standards
description: Python coding standards for Amplifier including type hints, async patterns, error handling, and formatting. Use when writing Python code for Amplifier modules.
version: 1.0.0
license: MIT
metadata:
  category: development
  complexity: low
---

# Python Coding Standards

## Type Hints

**ALL functions must have complete type hints:**

```python
from typing import Any

async def process_data(items: list[str], config: dict[str, Any]) -> dict[str, Any]:
    """Process data items with configuration."""
    results = {}
    for item in items:
        results[item] = await transform(item, config)
    return results
```

**Include type hints for self:**

```python
class MyClass:
    def __init__(self: "MyClass", name: str) -> None:
        self.name = name

    async def process(self: "MyClass") -> str:
        return f"Processing {self.name}"
```

## Async Patterns

**All I/O operations must be async:**

```python
# Good
async def read_file(path: Path) -> str:
    content = path.read_text()  # For now, sync is OK
    return content

# Better (when using async libraries)
async def read_file(path: Path) -> str:
    async with aiofiles.open(path) as f:
        return await f.read()
```

**Use asyncio.gather for parallel operations:**

```python
async def process_files(files: list[Path]) -> list[dict]:
    tasks = [process_file(f) for f in files]
    return await asyncio.gather(*tasks)
```

## Error Handling

**Return errors, don't raise:**

```python
from amplifier_core import ToolResult

async def execute(self: "MyTool", input: dict[str, Any]) -> ToolResult:
    """Execute tool operation."""
    try:
        result = await self._process(input)
        return ToolResult(success=True, output=result)
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        return ToolResult(success=False, error={"message": str(e)})
```

**Provide clear error messages:**

```python
# Good
return ToolResult(
    success=False,
    error={"message": f"File not found: {path}"}
)

# Bad
return ToolResult(
    success=False,
    error={"message": "Error"}
)
```

## Formatting

**Line length: 120 characters**

**Import organization:**

```python
# Standard library
import asyncio
import logging
from pathlib import Path
from typing import Any

# Third-party
import yaml
from pydantic import BaseModel

# Local/Amplifier
from amplifier_core import ModuleCoordinator, ToolResult
```

**Files must end with newline** - Add blank line at EOF

**Use ruff for formatting:**

```bash
uv run ruff format .
uv run ruff check . --fix
```

## Dependencies

**Use uv for dependency management:**

```bash
# Add dependency
cd amplifier-module-tool-mytool
uv add package-name

# Add dev dependency
uv add --dev pytest ruff pyright
```

**Never manually edit pyproject.toml dependencies** - Use `uv add`

## Testing

**Test behavior at protocol level:**

```python
import pytest
from amplifier_core.testing import TestCoordinator

@pytest.mark.asyncio
async def test_tool_basic():
    """Test basic tool functionality."""
    coordinator = TestCoordinator()

    # Mount module
    await mount(coordinator, {"timeout": 10})

    # Get and test
    tool = coordinator.get("tools", "my-tool")
    result = await tool.execute({"param": "value"})

    assert result.success
    assert "expected" in result.output
```

**Test pyramid: 60% unit, 30% integration, 10% end-to-end**

## Common Pitfalls

### Don't use blocking I/O

```python
# Bad
content = requests.get(url).text

# Good
async with aiohttp.ClientSession() as session:
    async with session.get(url) as response:
        content = await response.text()
```

### Don't modify module internals from outside

```python
# Bad
tool._internal_state = new_value

# Good
await tool.execute({"operation": "update", "value": new_value})
```

### Don't put logic in mount()

```python
# Bad
async def mount(coordinator, config):
    tool = MyTool()
    await tool.initialize_database()  # Heavy logic
    await coordinator.mount("tools", tool)

# Good
async def mount(coordinator, config):
    tool = MyTool(config)  # Light initialization only
    await coordinator.mount("tools", tool)
    # Heavy logic happens in execute(), not mount()
```

## Remember

- Run `make check` before committing
- Keep modules focused and simple
- Document public interfaces
- Test at the protocol level
