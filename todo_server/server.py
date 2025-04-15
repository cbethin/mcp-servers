import logging
from mcp.server.fastmcp import FastMCP
from typing import List, Dict, Any, Optional
from utils.todo_manager import (
    get_todos as tm_todo_list,
    add_todo as tm_todo_create,
    toggle_todo as tm_todo_toggle_completion,
    delete_todo as tm_todo_delete,
    get_subtree as tm_todo_get_with_subtasks,
    update_subtree as tm_todo_update,
    move_subtree as tm_todo_move,
    create_context as tm_context_create,
    delete_context as tm_context_delete,
    get_contexts as tm_context_list,
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger = logging.getLogger("todo_server")

mcp = FastMCP("todo_server")

# Context Management
@mcp.tool()
def context_create(name: str, description: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a new context session for organizing todo items.
    
    A context represents a separate workspace or project area for todos. 
    Each context has its own set of todos that can be managed independently.
    
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
    Delete a context and all its associated todos permanently.
    
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

@mcp.tool()
def context_list() -> List[Dict[str, Any]]:
    """
    List all available contexts in the system.
    
    IMPORTANT: Always call this tool first before interacting with todos. This ensures you know which contexts are available and can select the appropriate one for further actions.
    
    Returns a list of all contexts, including the default context which is always present.
    Each context contains todos that can be accessed via todo_list().
    
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

# Todo CRUD Operations
@mcp.tool()
def todo_create(title: str, description: Optional[str] = None, deadline: Optional[str] = None, 
                parent_id: Optional[int] = None, context_id: Optional[str] = None, how_to_guide: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a new todo item within a specific context.
    
    The description should be short and to the point. Use how_to_guide for detailed, step-by-step instructions or explanations in markdown format. Do not repeat information between the description, how_to_guide, and subtasks. If you provide a how_to_guide, do not create subtasks for the same steps covered in the guide—choose one approach for detailed steps. Only apply a how_to_guide to edge (leaf) todos that do not have subtasks; parent todos with subtasks should not have a how_to_guide.
    The how_to_guide should include enough information to pickup the task without any additional context (so should include all the context necessary)
    
    Args:
        title: The title/name of the todo item (required)
        description: Short summary of what the todo involves (keep it brief)
        deadline: Optional deadline in ISO format (e.g., "2025-04-30T23:59:59")
        parent_id: If provided, creates this todo as a subtask of the todo with this ID
        context_id: The context to add this todo to (uses default context if not specified)
        how_to_guide: Markdown-formatted detailed instructions for the task (only for leaf todos)
    
    Returns:
        Dict containing the newly created todo with fields:
        - id: Unique numeric identifier
        - title: The title provided
        - description: The description provided
        - deadline: The deadline if provided
        - completed: Always false for new todos
        - created_at: Timestamp when created
        - how_to_guide: The markdown guide if provided
        - subtasks: Empty list for new todos
    
    Example:
        todo_create(
            title="Implement login feature",
            description="Create login page with username/password fields",
            deadline="2025-05-01T17:00:00",
            how_to_guide="## Login Implementation\n1. Create form\n2. Add validation\n3. Connect to backend"
        )
    """
    try:
        return tm_todo_create(title, description or "", deadline, parent_id, context_id, how_to_guide or "")
    except Exception as e:
        logger.exception("Error in todo_create")
        return {"error": str(e)}

@mcp.tool()
def todo_update(id: int, title: Optional[str] = None, description: Optional[str] = None, 
                deadline: Optional[str] = None, completed: Optional[bool] = None,
                context_id: Optional[str] = None, how_to_guide: Optional[str] = None) -> Dict[str, Any]:
    """
    Update a todo's properties while preserving its subtasks structure.
    
    The description should be short and to the point. Use how_to_guide for detailed, step-by-step instructions or explanations in markdown format. Do not repeat information between the description, how_to_guide, and subtasks. If you provide a how_to_guide, do not create subtasks for the same steps covered in the guide—choose one approach for detailed steps. Only apply a how_to_guide to edge (leaf) todos that do not have subtasks; parent todos with subtasks should not have a how_to_guide.
    
    Args:
        id: The unique ID of the todo to update (required)
        title: New title if you want to change it
        description: Short summary (keep it brief)
        deadline: New deadline in ISO format (or null to remove deadline)
        completed: New completion status (True/False)
        context_id: The context to search in (uses default if not specified)
        how_to_guide: New markdown-formatted detailed instructions for the task (only for leaf todos)
    
    Returns:
        Dict containing the updated todo with all fields (including unchanged ones)
        or an error message if the todo wasn't found:
        - On error: {"error": "Error message"}
    
    Example:
        todo_update(
            id=42,
            title="Updated: Implement login feature",
            completed=True,
            how_to_guide="## Revised Login Implementation\n1. Use OAuth instead\n2. Add SSO support"
        )
    """
    try:
        return tm_todo_update(id, title, description, deadline, completed, how_to_guide, context_id)
    except Exception as e:
        logger.exception("Error in todo_update")
        return {"error": str(e)}

@mcp.tool()
def todo_delete(id: int, context_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Delete a todo item and all its subtasks permanently.
    
    This operation cannot be undone. If you delete a todo that has subtasks,
    all subtasks will also be deleted.
    
    Args:
        id: The unique ID of the todo item to delete (required)
        context_id: The context to search in (uses default if not specified)
    
    Returns:
        Dict with success or error message:
        - On success: {"success": True, "message": "Todo 'TITLE' deleted"}
        - On error: {"error": "Error message"}
    
    Example:
        todo_delete(id=42)
    """
    try:
        return tm_todo_delete(id, context_id)
    except Exception as e:
        logger.exception("Error in todo_delete")
        return {"error": str(e)}

@mcp.tool()
def todo_get(id: int, context_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Get a specific todo item and its entire subtask hierarchy.
    
    Retrieves comprehensive information about a todo, including its complete
    subtask tree with all properties of each subtask.
    
    Args:
        id: The unique ID of the todo to retrieve (required)
        context_id: The context to search in (uses default if not specified)
    
    Returns:
        Complete todo object with all fields and all nested subtasks
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
        return tm_todo_get_with_subtasks(id, context_id)
    except Exception as e:
        logger.exception("Error in todo_get")
        return {"error": str(e)}

@mcp.tool()
def todo_list(context_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    List all top-level todos in a specific context.
    
    Returns all root-level todos in the specified context (or default context).
    Each todo includes its full subtask hierarchy.
    
    Args:
        context_id: The context to list todos from (uses default if not specified)
    
    Returns:
        List of todo objects, each containing all fields and its subtask hierarchy.
        Returns an empty list if no todos exist or if the context doesn't exist.
    
    Example:
        todo_list(context_id="work-context")
    """
    try:
        return tm_todo_list(context_id)
    except Exception as e:
        logger.exception("Error in todo_list")
        return []

# Todo Specialized Operations
@mcp.tool()
def todo_toggle_completion(id: int, recursive: bool = False, context_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Toggle the completed status of a todo item (and optionally all its subtasks).
    
    Changes a todo's status from incomplete to complete or vice versa.
    If recursive=True, all subtasks will be set to the same status as the parent.
    
    Args:
        id: The unique ID of the todo item to toggle (required)
        recursive: If True, also toggle all subtasks to match the parent's new status
        context_id: The context to search in (uses default if not specified)
    
    Returns:
        Dict containing the updated todo with all fields
        or an error message if the todo wasn't found:
        - On error: {"error": "Error message"}
    
    Example:
        todo_toggle_completion(id=42, recursive=True)
    """
    try:
        return tm_todo_toggle_completion(id, recursive, context_id)
    except Exception as e:
        logger.exception("Error in todo_toggle_completion")
        return {"error": str(e)}

@mcp.tool()
def todo_move(id: int, new_parent_id: Optional[int] = None, 
              source_context_id: Optional[str] = None, 
              target_context_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Move a todo and its subtasks to a new parent or to root level, optionally between contexts.
    
    This function allows for complex reorganization of the todo hierarchy:
    - Move a subtask to become a root-level todo
    - Move a root todo to become a subtask of another todo
    - Move a subtask to become a subtask of a different parent
    - Move todos between different contexts
    
    Args:
        id: The unique ID of the todo subtree to move (required)
        new_parent_id: The ID of the new parent, or None to move to root level
        source_context_id: The context to move from (uses default if not specified)
        target_context_id: The context to move to (uses source_context_id if not specified)
    
    Returns:
        Dict containing the moved todo (with all subtasks)
        or an error message if operation failed:
        - On error: {"error": "Error message"}
    
    Constraints:
    - Cannot move a todo to be its own child
    - Cannot move a todo to be a child of one of its own descendants
    
    Example:
        todo_move(id=42, new_parent_id=50, target_context_id="work-context")
    """
    try:
        return tm_todo_move(id, new_parent_id, source_context_id, target_context_id)
    except Exception as e:
        logger.exception("Error in todo_move")
        return {"error": str(e)}

# Resources (for RESTful access)
@mcp.resource("todo-server://contexts")
def resource_context_list() -> List[Dict[str, Any]]:
    """
    Resource: List all available contexts.
    """
    try:
        return tm_context_list()
    except Exception as e:
        logger.exception("Error in resource_context_list")
        return []

@mcp.resource("todo-server://todos/default")
def resource_default_todo_list() -> List[Dict[str, Any]]:
    """
    Resource: List all todos in the default context.
    """
    try:
        return tm_todo_list()
    except Exception as e:
        logger.exception("Error in resource_default_todo_list")
        return []

@mcp.resource("todo-server://todos/{context_id}")
def resource_context_todo_list(context_id: str) -> List[Dict[str, Any]]:
    """
    Resource: List all todos in a specific context.
    """
    try:
        return tm_todo_list(context_id)
    except Exception as e:
        logger.exception("Error in resource_context_todo_list")
        return []