"""
Integration tests for the Sandbox Terminal MCP Server
"""

import unittest
import tempfile
import shutil
from pathlib import Path
import json
import time

from server import (
    sandbox_create, sandbox_list, sandbox_execute,
    sandbox_read_file, sandbox_write_file, sandbox_list_files,
    sandbox_diff, sandbox_reset, sandbox_destroy
)

# Import async helper for async tools
from tests.async_helper import sync_run_async_tool


class TestSandboxIntegration(unittest.TestCase):
    """Integration tests for the full sandbox workflow."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment once for all tests."""
        cls.test_project = tempfile.mkdtemp(prefix="test_project_")
        
        # Create a mock project structure
        Path(cls.test_project, "README.md").write_text("# Test Project\n\nThis is a test.")
        Path(cls.test_project, "package.json").write_text(json.dumps({
            "name": "test-project",
            "version": "1.0.0",
            "scripts": {
                "test": "echo 'Running tests...'",
                "build": "echo 'Building project...'"
            }
        }, indent=2))
        
        Path(cls.test_project, "src").mkdir()
        Path(cls.test_project, "src", "index.js").write_text("""
console.log('Hello from test project!');

function add(a, b) {
    return a + b;
}

module.exports = { add };
""")
        
        Path(cls.test_project, "src", "utils.js").write_text("""
function formatDate(date) {
    return date.toISOString();
}

module.exports = { formatDate };
""")
        
        Path(cls.test_project, "tests").mkdir()
        Path(cls.test_project, "tests", "test.js").write_text("""
const { add } = require('../src/index');

console.log('Testing add function...');
console.assert(add(2, 3) === 5, 'Add function failed');
console.log('Tests passed!');
""")
        
    @classmethod
    def tearDownClass(cls):
        """Clean up test environment."""
        shutil.rmtree(cls.test_project, ignore_errors=True)
        
    def setUp(self):
        """Set up for each test."""
        self.sandbox_name = f"test_sandbox_{int(time.time() * 1000)}"
        
    def tearDown(self):
        """Clean up after each test."""
        # Try to destroy the sandbox if it exists
        try:
            sandbox_destroy(self.sandbox_name)
        except:
            pass
            
    def test_complete_workflow(self):
        """Test a complete workflow from creation to destruction."""
        # 1. Create sandbox
        result = sync_run_async_tool(sandbox_create(self.test_project, self.sandbox_name))
        self.assertTrue(result["success"])
        self.assertEqual(result["session_name"], self.sandbox_name)
        
        # 2. List sandboxes
        sandboxes = sandbox_list()
        sandbox_names = [s["name"] for s in sandboxes]
        self.assertIn(self.sandbox_name, sandbox_names)
        
        # 3. Execute commands
        result = sync_run_async_tool(sandbox_execute(self.sandbox_name, "ls -la"))
        self.assertTrue(result["success"])
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("README.md", result["output"])
        self.assertIn("package.json", result["output"])
        
        # 4. Read a file
        result = sandbox_read_file(self.sandbox_name, "package.json")
        self.assertTrue(result["success"])
        package_data = json.loads(result["content"])
        self.assertEqual(package_data["name"], "test-project")
        
        # 5. Write a new file
        new_content = "export const VERSION = '1.0.0';"
        result = sandbox_write_file(self.sandbox_name, "src/version.js", new_content)
        self.assertTrue(result["success"])
        self.assertEqual(result["bytes_written"], len(new_content.encode()))
        
        # 6. List files in src directory
        result = sandbox_list_files(self.sandbox_name, "src")
        self.assertTrue(result["success"])
        file_names = [f["name"] for f in result["files"]]
        self.assertIn("index.js", file_names)
        self.assertIn("version.js", file_names)
        
        # 7. Check diff
        result = sandbox_diff(self.sandbox_name)
        self.assertTrue(result["success"])
        self.assertIn("src/version.js", result["changes"]["added"])
        self.assertEqual(len(result["changes"]["added"]), 1)
        
        # 8. Destroy sandbox
        result = sandbox_destroy(self.sandbox_name)
        self.assertTrue(result["success"])
        
        # Verify it's gone
        sandboxes = sandbox_list()
        sandbox_names = [s["name"] for s in sandboxes]
        self.assertNotIn(self.sandbox_name, sandbox_names)
        
    def test_build_process_simulation(self):
        """Test simulating a build process."""
        # Create sandbox
        sync_run_async_tool(sandbox_create(self.test_project, self.sandbox_name))
        
        # Modify package.json to add a dependency
        result = sandbox_read_file(self.sandbox_name, "package.json")
        package_data = json.loads(result["content"])
        package_data["dependencies"] = {"lodash": "^4.17.21"}
        
        result = sandbox_write_file(
            self.sandbox_name,
            "package.json",
            json.dumps(package_data, indent=2)
        )
        self.assertTrue(result["success"])
        
        # Create a build output directory
        result = sync_run_async_tool(sandbox_execute(self.sandbox_name, "mkdir -p dist"))
        self.assertTrue(result["success"])
        
        # Simulate build output
        build_output = """
(function() {
    console.log('Bundled application');
    // ... bundled code ...
})();
"""
        result = sandbox_write_file(self.sandbox_name, "dist/bundle.js", build_output)
        self.assertTrue(result["success"])
        
        # Check the changes
        result = sandbox_diff(self.sandbox_name)
        self.assertIn("package.json", result["changes"]["modified"])
        self.assertIn("dist/bundle.js", result["changes"]["added"])
        
        # Clean up
        sandbox_destroy(self.sandbox_name)
        
    def test_command_execution_scenarios(self):
        """Test various command execution scenarios."""
        sync_run_async_tool(sandbox_create(self.test_project, self.sandbox_name))
        
        # Test working directory
        result = sync_run_async_tool(sandbox_execute(self.sandbox_name, "pwd"))
        self.assertIn("workspace", result["output"])
        
        # Test changing to subdirectory
        result = sync_run_async_tool(sandbox_execute(self.sandbox_name, "pwd", working_dir="src"))
        self.assertIn("src", result["output"])
        
        # Test command with output
        result = sync_run_async_tool(sandbox_execute(self.sandbox_name, "echo 'Hello World'"))
        self.assertIn("Hello World", result["output"])
        
        # Test command failure
        result = sync_run_async_tool(sandbox_execute(self.sandbox_name, "exit 42"))
        self.assertFalse(result["success"])
        self.assertEqual(result["exit_code"], 42)
        
        # Test piped commands
        result = sync_run_async_tool(sandbox_execute(self.sandbox_name, "ls | grep js | wc -l"))
        self.assertTrue(result["success"])
        # Should find at least index.js and utils.js
        
        # Clean up
        sandbox_destroy(self.sandbox_name)
        
    def test_file_operations(self):
        """Test various file operations."""
        sync_run_async_tool(sandbox_create(self.test_project, self.sandbox_name))
        
        # Test reading non-existent file
        result = sandbox_read_file(self.sandbox_name, "nonexistent.txt")
        self.assertFalse(result["success"])
        self.assertIn("not found", result["error"])
        
        # Test creating nested directories
        result = sandbox_write_file(
            self.sandbox_name,
            "config/deep/nested/config.json",
            '{"nested": true}'
        )
        self.assertTrue(result["success"])
        
        # Verify nested file exists
        result = sandbox_list_files(self.sandbox_name, "config/deep/nested")
        self.assertTrue(result["success"])
        self.assertEqual(len(result["files"]), 1)
        self.assertEqual(result["files"][0]["name"], "config.json")
        
        # Test listing root directory
        result = sandbox_list_files(self.sandbox_name, "/")
        self.assertTrue(result["success"])
        dir_names = [f["name"] for f in result["files"] if f["type"] == "directory"]
        self.assertIn("src", dir_names)
        self.assertIn("tests", dir_names)
        self.assertIn("config", dir_names)
        
        # Clean up
        sandbox_destroy(self.sandbox_name)
        
    def test_reset_functionality(self):
        """Test sandbox reset functionality."""
        sync_run_async_tool(sandbox_create(self.test_project, self.sandbox_name))
        
        # Make several changes
        sandbox_write_file(self.sandbox_name, "new_file.txt", "New content")
        sandbox_write_file(self.sandbox_name, "README.md", "Modified readme")
        sync_run_async_tool(sandbox_execute(self.sandbox_name, "rm package.json"))
        sync_run_async_tool(sandbox_execute(self.sandbox_name, "mkdir temp_dir"))
        
        # Verify changes
        result = sandbox_diff(self.sandbox_name)
        self.assertGreater(len(result["changes"]["added"]), 0)
        self.assertGreater(len(result["changes"]["modified"]), 0)
        self.assertGreater(len(result["changes"]["deleted"]), 0)
        
        # Reset
        result = sandbox_reset(self.sandbox_name)
        self.assertTrue(result["success"])
        
        # Verify reset
        result = sandbox_diff(self.sandbox_name)
        self.assertEqual(len(result["changes"]["added"]), 0)
        self.assertEqual(len(result["changes"]["modified"]), 0)
        self.assertEqual(len(result["changes"]["deleted"]), 0)
        
        # Verify original content restored
        result = sandbox_read_file(self.sandbox_name, "README.md")
        self.assertIn("This is a test", result["content"])
        
        # Clean up
        sandbox_destroy(self.sandbox_name)
        
    def test_concurrent_sandboxes(self):
        """Test managing multiple sandboxes concurrently."""
        sandbox1 = f"{self.sandbox_name}_1"
        sandbox2 = f"{self.sandbox_name}_2"
        
        try:
            # Create two sandboxes
            result1 = sync_run_async_tool(sandbox_create(self.test_project, sandbox1))
            self.assertTrue(result1["success"])
            
            result2 = sync_run_async_tool(sandbox_create(self.test_project, sandbox2))
            self.assertTrue(result2["success"])
            
            # Make different changes in each
            sandbox_write_file(sandbox1, "sandbox1.txt", "Sandbox 1 content")
            sandbox_write_file(sandbox2, "sandbox2.txt", "Sandbox 2 content")
            
            # Verify isolation
            result = sandbox_list_files(sandbox1, "/")
            files1 = [f["name"] for f in result["files"]]
            self.assertIn("sandbox1.txt", files1)
            self.assertNotIn("sandbox2.txt", files1)
            
            result = sandbox_list_files(sandbox2, "/")
            files2 = [f["name"] for f in result["files"]]
            self.assertIn("sandbox2.txt", files2)
            self.assertNotIn("sandbox1.txt", files2)
            
        finally:
            # Clean up both sandboxes
            try:
                sandbox_destroy(sandbox1)
            except:
                pass
            try:
                sandbox_destroy(sandbox2)
            except:
                pass
                
    def test_error_handling(self):
        """Test error handling in various scenarios."""
        # Test creating sandbox with invalid source
        result = sync_run_async_tool(sandbox_create("/nonexistent/path", self.sandbox_name))
        self.assertFalse(result["success"])
        self.assertIn("error", result)
        
        # Test operations on non-existent sandbox
        result = sync_run_async_tool(sandbox_execute("nonexistent_sandbox", "ls"))
        self.assertFalse(result["success"])
        
        result = sandbox_read_file("nonexistent_sandbox", "file.txt")
        self.assertFalse(result["success"])
        
        result = sandbox_diff("nonexistent_sandbox")
        self.assertFalse(result["success"])
        
    def test_command_safety(self):
        """Test that dangerous commands are blocked."""
        sync_run_async_tool(sandbox_create(self.test_project, self.sandbox_name))
        
        # Test dangerous commands
        dangerous_commands = [
            "rm -rf /",
            "shutdown",
            ":(){:|:&};:",  # Fork bomb
        ]
        
        for cmd in dangerous_commands:
            result = sync_run_async_tool(sandbox_execute(self.sandbox_name, cmd))
            self.assertFalse(result["success"])
            self.assertIn("blocked", result["error"].lower())
            
        # Clean up
        sandbox_destroy(self.sandbox_name)


if __name__ == "__main__":
    unittest.main()