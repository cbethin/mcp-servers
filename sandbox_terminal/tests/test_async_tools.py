"""
Test async tools functionality.
"""

import unittest
import asyncio
import tempfile
from pathlib import Path

from server import sandbox_create, sandbox_execute


class TestAsyncTools(unittest.TestCase):
    """Test async tool functionality."""
    
    async def _collect_yields(self, async_gen):
        """Collect all yielded values from an async generator."""
        yields = []
        async for value in async_gen:
            yields.append(value)
        return yields
    
    async def _run_async_tool(self, async_gen):
        """Run an async tool and return both yields and final result."""
        yields = []
        result = None
        
        async for value in async_gen:
            if isinstance(value, dict) and ("success" in value or "error" in value):
                # This is the final result
                result = value
            else:
                # This is a progress message
                yields.append(value)
        
        return yields, result
    
    def test_sandbox_create_async_tool(self):
        """Test sandbox_create as an async tool."""
        async def run_test():
            # Create a test directory
            with tempfile.TemporaryDirectory() as tmpdir:
                Path(tmpdir, "test.txt").write_text("Hello World")
                
                # Run sandbox_create
                yields, result = await self._run_async_tool(
                    sandbox_create(tmpdir, "test_async_sandbox")
                )
                
                # Check yields
                self.assertTrue(len(yields) > 0)
                self.assertIn("Starting sandbox creation", yields[0])
                
                # Check result
                self.assertTrue(result["success"])
                self.assertEqual(result["session_name"], "test_async_sandbox")
                
                return result
        
        # Run the async test
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(run_test())
        finally:
            loop.close()
    
    def test_sandbox_execute_async_tool(self):
        """Test sandbox_execute as an async tool."""
        async def run_test():
            # First create a sandbox (simplified for testing)
            with tempfile.TemporaryDirectory() as tmpdir:
                # Create sandbox first
                async for _ in sandbox_create(tmpdir, "test_exec_sandbox"):
                    pass  # Just consume the generator
                
                # Now test execute
                yields, result = await self._run_async_tool(
                    sandbox_execute("test_exec_sandbox", "echo 'Hello from async tool'")
                )
                
                # Check yields
                self.assertTrue(len(yields) > 0)
                self.assertIn("Executing command:", yields[0])
                self.assertTrue(any("completed successfully" in y for y in yields))
                
                # Check result
                self.assertTrue(result["success"])
                self.assertIn("Hello from async tool", result["output"])
                
                return result
        
        # Run the async test
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(run_test())
        finally:
            loop.close()


if __name__ == "__main__":
    unittest.main()