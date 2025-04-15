import logging
from mcp.server.fastmcp import FastMCP
from typing import List, Dict, Any, Optional
from utils.task_manager import (
    get_tasks as tm_task_list,
    add_task as tm_task_create,
    toggle_task as tm_task_toggle_completion,
    delete_task as tm_task_delete,
    get_subtree as tm_task_get_with_subtasks,
    update_subtree as tm_task_update,
    move_subtree as tm_task_move,
    create_context as tm_context_create,
    delete_context as tm_context_delete,
    get_contexts as tm_context_list,
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger = logging.getLogger("task_server")

mcp = FastMCP("task_server")

# Context Management
@mcp.tool()
def context_create(name: str, description: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a new context session for organizing task items.
    
    A context represents a separate workspace or project area for tasks. 
    Each context has its own set of tasks that can be managed independently.
    
    Args:
        name: The name of the context (e.g., "Work", "Personal", "Project X")
        description: An optional description providing more details about the context's purpose
    
    Returns:
        Dict containing the newly created context with fields:
        - id: A unique identifier for the context
        - name: The name provided
        - description: The description provided
        - created_at: Timestamp when the context was created
    
    Example:
        context_create("Work", "Tasks related to my job")
    """
    try:
        return tm_context_create(name, description or "")
    except Exception as e:
        logger.exception("Error in context_create")
        return {"error": str(e)}

@mcp.tool()
def context_delete(context_id: str) -> Dict[str, Any]:
    """
    Delete a context and all its associated tasks permanently.
    
    This operation cannot be undone. The default context cannot be deleted.
    
    Args:
        context_id: The unique identifier of the context to delete
    
    Returns:
        Dict with success or error message:
        - On success: {"success": True, "message": "Context 'NAME' deleted"}
        - On error: {"error": "Error message"}
    
    Example:
        context_delete("a1b2c3d4-e5f6-7890-abcd-1234567890ab")
    """
    try:
        return tm_context_delete(context_id)
    except Exception as e:
        logger.exception("Error in context_delete")
        return {"error": str(e)}

@mcp.resource("task-server://contexts")
def context_list() -> List[Dict[str, Any]]:
    """
    List all available contexts in the system.
    
    IMPORTANT: Always call this tool first before interacting with tasks. This ensures you know which contexts are available and can select the appropriate one for further actions.
    
    Returns a list of all contexts, including the default context which is always present.
    Each context contains tasks that can be accessed via task_list().
    
    Returns:
        List of context dictionaries, each containing:
        - id: The unique identifier for the context
        - name: The name of the context
        - description: Description of the context
        - created_at: When the context was created
    
    Example response:
        [
            {
                "id": "default",
                "name": "Default",
                "description": "Default context",
                "created_at": "2023-04-01T12:00:00.000000"
            },
            {
                "id": "a1b2c3d4-e5f6-7890-abcd-1234567890ab",
                "name": "Work",
                "description": "Work-related tasks",
                "created_at": "2023-04-15T09:30:00.000000"
            }
        ]
    """
    try:
        return tm_context_list()
    except Exception as e:
        logger.exception("Error in context_list")
        return []

# Task CRUD Operations
@mcp.tool()
def task_create(title: str, description: Optional[str] = None, deadline: Optional[str] = None, 
                parent_id: Optional[int] = None, context_id: Optional[str] = None, how_to_guide: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a new task ("todo" item) within a specific context.
    
    A task is essentially a "todo" item—these terms are interchangeable in this MCP server. The description should be short and to the point. Use how_to_guide for detailed, step-by-step instructions or explanations in markdown format. Do not repeat information between the description, how_to_guide, and subtasks. If you provide a how_to_guide, do not create subtasks for the same steps covered in the guide—choose one approach for detailed steps. Only apply a how_to_guide to edge (leaf) tasks that do not have subtasks; parent tasks with subtasks should not have a how_to_guide.
    The how_to_guide should include enough information to pickup the task without any additional context (so should include all the context necessary)
    
    Args:
        title: The title/name of the task ("todo" item) (required)
        description: Short summary of what the task involves (keep it brief)
        deadline: Optional deadline in ISO format (e.g., "2025-04-30T23:59:59")
        parent_id: If provided, creates this task as a subtask of the task with this ID
        context_id: The context to add this task to (uses default context if not specified)
        how_to_guide: Markdown-formatted detailed instructions for the task (only for leaf tasks)
    
    Returns:
        Dict containing the newly created task ("todo" item) with fields:
        - id: Unique numeric identifier
        - title: The title provided
        - description: The description provided
        - deadline: The deadline if provided
        - completed: Always false for new tasks
        - created_at: Timestamp when created
        - how_to_guide: The markdown guide if provided
        - subtasks: Empty list for new tasks
    
    Example:
        task_create(
            title="Implement login feature",
            description="Create login page with username/password fields",
            deadline="2025-05-01T17:00:00",
            how_to_guide="## Login Implementation\n1. Create form\n2. Add validation\n3. Connect to backend"
        )
    """
    try:
        return tm_task_create(title, description or "", deadline, parent_id, context_id, how_to_guide or "")
    except Exception as e:
        logger.exception("Error in task_create")
        return {"error": str(e)}

@mcp.tool()
def task_update(id: int, title: Optional[str] = None, description: Optional[str] = None, 
                deadline: Optional[str] = None, completed: Optional[bool] = None,
                context_id: Optional[str] = None, how_to_guide: Optional[str] = None) -> Dict[str, Any]:
    """
    Update a task ("todo" item)'s properties while preserving its subtasks structure.
    
    A task is essentially a "todo" item—these terms are interchangeable in this MCP server. The description should be short and to the point. Use how_to_guide for detailed, step-by-step instructions or explanations in markdown format. Do not repeat information between the description, how_to_guide, and subtasks. If you provide a how_to_guide, do not create subtasks for the same steps covered in the guide—choose one approach for detailed steps. Only apply a how_to_guide to edge (leaf) tasks that do not have subtasks; parent tasks with subtasks should not have a how_to_guide.
    
    Args:
        id: The unique ID of the task ("todo" item) to update (required)
        title: New title if you want to change it
        description: Short summary (keep it brief)
        deadline: New deadline in ISO format (or null to remove deadline)
        completed: New completion status (True/False)
        context_id: The context to search in (uses default if not specified)
        how_to_guide: New markdown-formatted detailed instructions for the task (only for leaf tasks)
    
    Returns:
        Dict containing the updated task ("todo" item) with all fields (including unchanged ones)
        or an error message if the task wasn't found:
        - On error: {"error": "Error message"}
    
    Example:
        task_update(
            id=42,
            title="Updated: Implement login feature",
            completed=True,
            how_to_guide="## Revised Login Implementation\n1. Use OAuth instead\n2. Add SSO support"
        )
    """
    try:
        return tm_task_update(id, title, description, deadline, completed, how_to_guide, context_id)
    except Exception as e:
        logger.exception("Error in task_update")
        return {"error": str(e)}

@mcp.tool()
def task_delete(id: int, context_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Delete a task ("todo" item) and all its subtasks permanently.
    
    A task is essentially a "todo" item—these terms are interchangeable in this MCP server. This operation cannot be undone. If you delete a task that has subtasks, all subtasks will also be deleted.
    
    Args:
        id: The unique ID of the task ("todo" item) to delete (required)
        context_id: The context to search in (uses default if not specified)
    
    Returns:
        Dict with success or error message:
        - On success: {"success": True, "message": "Task 'TITLE' deleted"}
        - On error: {"error": "Error message"}
    
    Example:
        task_delete(id=42)
    """
    try:
        return tm_task_delete(id, context_id)
    except Exception as e:
        logger.exception("Error in task_delete")
        return {"error": str(e)}

@mcp.resource("task-server://tasks/{id}")
def task_get(id: int) -> Dict[str, Any]:
    """
    Get a specific task ("todo" item) and its entire subtask hierarchy.
    
    A task is essentially a "todo" item—these terms are interchangeable in this MCP server. Retrieves comprehensive information about a task, including its complete subtask tree with all properties of each subtask.
    
    Args:
        id: The unique ID of the task ("todo" item) to retrieve (required)
    
    Returns:
        Complete task ("todo" item) object with all fields and all nested subtasks
        or an error message if not found:
        - On error: {"error": "Error message"}
    
    Example response:
    {
        "id": 42,
        "title": "Implement feature X",
        "description": "Create new functionality",
        "deadline": "2025-05-01T17:00:00",
        "completed": false,
        "created_at": "2025-04-15T10:00:00.123456",
        "how_to_guide": "## Steps\n1. First step\n2. Second step",
        "subtasks": [
            {
                "id": 43,
                "title": "Subtask 1",
                "description": "Part of the implementation",
                "deadline": null,
                "completed": true,
                "created_at": "2025-04-15T10:05:00.123456",
                "how_to_guide": "",
                "subtasks": []
            }
        ]
    }
    """
    try:
        return tm_task_get_with_subtasks(id)
    except Exception as e:
        logger.exception("Error in task_get")
        return {"error": str(e)}

@mcp.resource("task-server://tasks/{context_id}")
def task_list(context_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    List all top-level tasks ("todo" items) in a specific context.
    
    A task is essentially a "todo" item—these terms are interchangeable in this MCP server. Returns all root-level tasks in the specified context (or default context). Each task includes its full subtask hierarchy.
    
    Args:
        context_id: The context to list tasks ("todo" items) from (uses default if not specified)
    
    Returns:
        List of task ("todo" item) objects, each containing all fields and its subtask hierarchy.
        Returns an empty list if no tasks exist or if the context doesn't exist.
    
    Example:
        task_list(context_id="work-context")
    """
    try:
        return tm_task_list(context_id)
    except Exception as e:
        logger.exception("Error in task_list")
        return []

# Task Specialized Operations
@mcp.tool()
def task_toggle_completion(id: int, recursive: bool = False, context_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Toggle the completed status of a task item (and optionally all its subtasks).
    
    Changes a task's status from incomplete to complete or vice versa.
    If recursive=True, all subtasks will be set to the same status as the parent.
    
    Args:
        id: The unique ID of the task item to toggle (required)
        recursive: If True, also toggle all subtasks to match the parent's new status
        context_id: The context to search in (uses default if not specified)
    
    Returns:
        Dict containing the updated task with all fields
        or an error message if the task wasn't found:
        - On error: {"error": "Error message"}
    
    Example:
        task_toggle_completion(id=42, recursive=True)
    """
    try:
        return tm_task_toggle_completion(id, recursive, context_id)
    except Exception as e:
        logger.exception("Error in task_toggle_completion")
        return {"error": str(e)}

@mcp.tool()
def task_move(id: int, new_parent_id: Optional[int] = None, 
              source_context_id: Optional[str] = None, 
              target_context_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Move a task and its subtasks to a new parent or to root level, optionally between contexts.
    
    This function allows for complex reorganization of the task hierarchy:
    - Move a subtask to become a root-level task
    - Move a root task to become a subtask of another task
    - Move a subtask to become a subtask of a different parent
    - Move tasks between different contexts
    
    Args:
        id: The unique ID of the task subtree to move (required)
        new_parent_id: The ID of the new parent, or None to move to root level
        source_context_id: The context to move from (uses default if not specified)
        target_context_id: The context to move to (uses source_context_id if not specified)
    
    Returns:
        Dict containing the moved task (with all subtasks)
        or an error message if operation failed:
        - On error: {"error": "Error message"}
    
    Constraints:
    - Cannot move a task to be its own child
    - Cannot move a task to be a child of one of its own descendants
    
    Example:
        task_move(id=42, new_parent_id=50, target_context_id="work-context")
    """
    try:
        return tm_task_move(id, new_parent_id, source_context_id, target_context_id)
    except Exception as e:
        logger.exception("Error in task_move")
        return {"error": str(e)}