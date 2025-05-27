# Testing Guide for Sandbox Terminal MCP Server

## Overview

The sandbox terminal server includes a comprehensive test suite with unit tests for each component and integration tests for the full workflow.

## Test Structure

```
tests/
├── __init__.py
├── test_session_store.py      # Tests for session persistence
├── test_file_tracker.py       # Tests for file change tracking
├── test_command_runner.py     # Tests for command safety validation
├── test_sandbox_manager.py    # Tests for sandbox orchestration
└── test_integration.py        # End-to-end integration tests
```

## Running Tests

### Run all tests:
```bash
python run_tests.py
```

### Run specific test module:
```bash
python run_tests.py test_session_store
```

### Run with different verbosity:
```bash
python run_tests.py -v  # Verbose
python run_tests.py -q  # Quiet
```

### Using pytest (if installed):
```bash
pytest tests/
pytest tests/test_command_runner.py::TestCommandRunner::test_safe_commands
```

### Using unittest directly:
```bash
python -m unittest discover tests
python -m unittest tests.test_session_store.TestSessionStore
```

## Test Coverage

### Unit Tests

1. **SessionStore** (13 tests)
   - Session CRUD operations
   - Command history tracking
   - Persistence across restarts
   - Old session cleanup
   - Size calculations

2. **FileChangeTracker** (16 tests)
   - Directory snapshots
   - Change detection (add/modify/delete)
   - Ignore patterns
   - Snapshot save/load
   - Large file handling

3. **CommandRunner** (13 tests)
   - Safe command validation
   - Dangerous command blocking
   - Pattern matching
   - Environment sanitization
   - Custom block lists

4. **SandboxManager** (19 tests)
   - Sandbox creation/destruction
   - Command execution
   - File operations
   - Resource limits
   - Docker integration (mocked)

### Integration Tests (8 tests)

- Complete workflow from creation to destruction
- Build process simulation
- Command execution scenarios
- File operations
- Reset functionality
- Concurrent sandboxes
- Error handling
- Command safety

## Test Results

All 67 tests pass successfully:
```
Ran 67 tests in 0.262s

OK
```

## Writing New Tests

When adding new features, include corresponding tests:

```python
import unittest
from utils.your_module import YourClass

class TestYourFeature(unittest.TestCase):
    def setUp(self):
        """Set up test environment."""
        self.instance = YourClass()
        
    def tearDown(self):
        """Clean up after tests."""
        # Cleanup code
        
    def test_feature_behavior(self):
        """Test specific behavior."""
        result = self.instance.method()
        self.assertEqual(result, expected_value)
```

## Testing Without Docker

The tests are designed to work without Docker by using subprocess fallback. Docker functionality is mocked in unit tests to avoid requiring Docker for testing.

## Continuous Integration

The test suite is designed to be CI-friendly:
- No external dependencies required for unit tests
- Automatic cleanup of test artifacts
- Deterministic test execution
- Clear pass/fail status

## Common Test Patterns

### Testing File Operations
```python
# Create test directory
test_dir = tempfile.mkdtemp()
try:
    # Test file operations
    Path(test_dir, "test.txt").write_text("content")
    # Assertions
finally:
    shutil.rmtree(test_dir)
```

### Testing Command Safety
```python
dangerous_commands = ["rm -rf /", "shutdown"]
for cmd in dangerous_commands:
    is_safe, reason = runner.is_command_safe(cmd)
    self.assertFalse(is_safe)
```

### Testing Session Management
```python
session = store.create_session("test", "/path")
# Perform operations
store.delete_session("test")
```

## Debugging Tests

To debug a specific test:
```bash
python -m pdb -m unittest tests.test_module.TestClass.test_method
```

Or add breakpoints in code:
```python
import pdb; pdb.set_trace()
```