import json
import os
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
from copy import deepcopy
import uuid
from anytree import Node, PreOrderIter

# Global data structures
contexts: List[Dict[str, Any]] = []
todos_by_context: Dict[str, List[Node]] = {}
next_id = 1
default_context_id = "default"

# --- AnyTree Conversion Helpers ---
def dict_to_tree(todo_dict, parent=None):
    """Recursively convert a todo dict (with subtasks) to an anytree Node tree."""
    node = Node(
        None,
        id=todo_dict["id"],
        title=todo_dict["title"],
        description=todo_dict.get("description", ""),
        deadline=todo_dict.get("deadline"),
        completed=todo_dict.get("completed", False),
        created_at=todo_dict.get("created_at"),
        how_to_guide=todo_dict.get("how_to_guide", ""),
        parent=parent
    )
    for sub in todo_dict.get("subtasks", []):
        dict_to_tree(sub, parent=node)
    return node

def tree_to_dict(node):
    """Recursively convert an anytree Node tree to a todo dict (with subtasks)."""
    d = {
        "id": node.id,
        "title": node.title,
        "description": node.description,
        "deadline": node.deadline,
        "completed": node.completed,
        "created_at": node.created_at,
        "how_to_guide": node.how_to_guide,
        "subtasks": [tree_to_dict(child) for child in node.children]
    }
    return d

def load_todos():
    global todos_by_context, contexts, next_id, default_context_id
    try:
        if os.path.exists("todos.json"):
            with open("todos.json", "r") as f:
                old_todos = json.load(f)
            if isinstance(old_todos, dict) and "contexts" in old_todos:
                contexts = old_todos["contexts"]
                # Convert dicts to Node trees
                todos_by_context = {
                    ctx: [dict_to_tree(todo) for todo in todo_list]
                    for ctx, todo_list in old_todos["todos_by_context"].items()
                }
                default_context_exists = any(c["id"] == default_context_id for c in contexts)
                if not default_context_exists:
                    contexts.append({
                        "id": default_context_id,
                        "name": "Default",
                        "description": "Default context",
                        "created_at": datetime.now().isoformat()
                    })
            else:
                contexts = [{
                    "id": default_context_id,
                    "name": "Default",
                    "description": "Default context",
                    "created_at": datetime.now().isoformat()
                }]
                todos_by_context = {default_context_id: [dict_to_tree(todo) for todo in old_todos]}
            # Find the highest ID
            max_id = 0
            for context_todos in todos_by_context.values():
                for root in context_todos:
                    for node in PreOrderIter(root):
                        max_id = max(max_id, getattr(node, "id", 0))
            next_id = max_id + 1
            save_todos()
    except Exception as e:
        print(f"Error loading todos: {e}")
        contexts = [{
            "id": default_context_id,
            "name": "Default",
            "description": "Default context",
            "created_at": datetime.now().isoformat()
        }]
        todos_by_context = {default_context_id: []}
        next_id = 1

def get_max_id(todo_list: List[Dict[str, Any]]) -> int:
    """Recursively find the highest ID in the todo tree."""
    max_id = 0
    for todo in todo_list:
        max_id = max(max_id, todo.get("id", 0))
        if "subtasks" in todo and todo["subtasks"]:
            subtask_max_id = get_max_id(todo["subtasks"])
            max_id = max(max_id, subtask_max_id)
    return max_id

def save_todos():
    try:
        with open("todos.json", "w") as f:
            json.dump({
                "contexts": contexts,
                "todos_by_context": {
                    ctx: [tree_to_dict(root) for root in todo_list]
                    for ctx, todo_list in todos_by_context.items()
                }
            }, f)
    except Exception as e:
        print(f"Error saving todos: {e}")

def create_context(name: str, description: str = "") -> Dict[str, Any]:
    """
    Create a new context session.
    
    Args:
        name: The name of the context
        description: Optional description
        
    Returns:
        The newly created context
    """
    global contexts, todos_by_context
    
    # Generate a unique ID for the context
    context_id = str(uuid.uuid4())
    
    new_context = {
        "id": context_id,
        "name": name,
        "description": description,
        "created_at": datetime.now().isoformat()
    }
    
    contexts.append(new_context)
    todos_by_context[context_id] = []
    
    save_todos()
    return new_context

def get_contexts() -> List[Dict[str, Any]]:
    """
    Get all available contexts.
    
    Returns:
        List of all contexts
    """
    return contexts

def delete_context(context_id: str) -> Dict[str, Any]:
    """
    Delete a context and all its todos.
    
    Args:
        context_id: The ID of the context to delete
        
    Returns:
        Success or error message
    """
    global contexts, todos_by_context
    
    # Cannot delete the default context
    if context_id == default_context_id:
        return {"error": "Cannot delete the default context"}
    
    # Find the context
    context_index = None
    for i, context in enumerate(contexts):
        if context["id"] == context_id:
            context_index = i
            break
    
    if context_index is None:
        return {"error": f"Context with ID {context_id} not found"}
    
    # Remove the context and its todos
    removed_context = contexts.pop(context_index)
    if context_id in todos_by_context:
        del todos_by_context[context_id]
    
    save_todos()
    return {"success": True, "message": f"Context '{removed_context['name']}' deleted"}

def add_todo(title: str, description: str = "", deadline: str = None, parent_id: int = None, context_id: str = default_context_id, how_to_guide: str = "") -> Dict[str, Any]:
    """
    Add a new todo, either as a root todo or as a subtask of another todo.
    
    The description should be short and to the point. Use how_to_guide for detailed, step-by-step instructions or explanations in markdown format.
    
    Args:
        title: The title of the todo
        description: Short summary (keep it brief)
        deadline: Optional deadline in ISO format
        parent_id: If provided, adds this todo as a subtask to the todo with this ID
        context_id: The context this todo belongs to
        how_to_guide: Optional markdown how-to guide for the todo (use for detailed instructions)
        
    Returns:
        The newly created todo
    """
    global todos_by_context, next_id
    err = get_context_or_error(context_id)
    if err:
        return err
    new_todo = Node(
        None,
        id=next_id,
        title=title,
        description=description or "",
        deadline=deadline,
        completed=False,
        created_at=datetime.now().isoformat(),
        how_to_guide=how_to_guide or "",
        subtasks=[]
    )
    next_id += 1
    if parent_id is None:
        todos_by_context[context_id].append(new_todo)
        save_todos()
        return tree_to_dict(new_todo)
    else:
        result = add_subtask(todos_by_context[context_id], parent_id, new_todo)
        if result:
            save_todos()
            return tree_to_dict(new_todo)
        return error_dict(f"Parent todo with ID {parent_id} not found in context {context_id}")

def add_subtask(todo_list: List[Node], parent_id: int, subtask: Node) -> bool:
    """Recursively search for a parent todo and add the subtask to it."""
    for todo in todo_list:
        if todo.id == parent_id:
            subtask.parent = todo
            return True
        if todo.children:
            if add_subtask(todo.children, parent_id, subtask):
                return True
    return False

def find_todo(todo_list: List[Node], id: int) -> Optional[Node]:
    """Find a todo by its ID using anytree's PreOrderIter for all roots."""
    for root in todo_list:
        for node in PreOrderIter(root):
            if node.id == id:
                return node
    return None

def find_todo_context(id: int) -> Optional[str]:
    """Find which context a todo belongs to using anytree's PreOrderIter."""
    for context_id, todos in todos_by_context.items():
        for root in todos:
            for node in PreOrderIter(root):
                if node.id == id:
                    return context_id
    return None

def toggle_todo(id: int, recursive: bool = False, context_id: Optional[str] = None) -> Union[Dict[str, Any], Dict[str, str]]:
    """
    Toggle the completion status of a todo. Optionally toggle all subtasks too.
    
    Args:
        id: The ID of the todo to toggle
        recursive: If True, also toggle all subtasks
        context_id: If provided, only search in this context
        
    Returns:
        The modified todo or an error message
    """
    if context_id:
        err = get_context_or_error(context_id)
        if err:
            return err
        todo = get_todo_or_error(todos_by_context[context_id], id, context_id)
        if isinstance(todo, dict):
            return todo
    else:
        context_id = find_todo_context(id)
        if not context_id:
            return error_dict(f"Todo with ID {id} not found in any context")
        todo = get_todo_or_error(todos_by_context[context_id], id, context_id)
        if isinstance(todo, dict):
            return todo
    todo.completed = not todo.completed
    if recursive and todo.children:
        toggle_subtasks(todo.children, todo.completed)
    save_todos()
    return tree_to_dict(todo)

def toggle_subtasks(subtasks: List[Node], completed: bool):
    """Recursively toggle all subtasks using anytree's PreOrderIter."""
    for subtask in subtasks:
        for node in PreOrderIter(subtask):
            node.completed = completed

def delete_todo(id: int, context_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Delete a todo by ID, whether it's a root todo or a subtask.
    
    Args:
        id: The ID of the todo to delete
        context_id: If provided, only search in this context
        
    Returns:
        Success or error message
    """
    if context_id:
        err = get_context_or_error(context_id)
        if err:
            return err
        # Try to delete from root level in this context
        for i, todo in enumerate(todos_by_context[context_id]):
            if todo.id == id:
                removed = todos_by_context[context_id].pop(i)
                save_todos()
                return {"success": True, "message": f"Todo '{removed.title}' deleted"}
        # If not found at root level, try to find and delete from subtasks
        result = delete_subtask(todos_by_context[context_id], id)
        if result:
            save_todos()
            return result
        return error_dict(f"Todo with ID {id} not found in context {context_id}")
    else:
        for ctx_id, todos in todos_by_context.items():
            for i, todo in enumerate(todos):
                if todo.id == id:
                    removed = todos.pop(i)
                    save_todos()
                    return {"success": True, "message": f"Todo '{removed.title}' deleted"}
            result = delete_subtask(todos, id)
            if result:
                save_todos()
                return result
        return error_dict(f"Todo with ID {id} not found in any context")

def delete_subtask(todo_list: List[Node], id: int) -> Optional[Dict[str, Any]]:
    """Recursively search for and delete a subtask."""
    for todo in todo_list:
        if todo.children:
            for i, subtask in enumerate(todo.children):
                if subtask.id == id:
                    removed = todo.children.pop(i)
                    return {"success": True, "message": f"Subtask '{removed.title}' deleted"}
            
            # If not found in immediate subtasks, search deeper
            for subtask in todo.children:
                result = delete_subtask(subtask.children, id)
                if result:
                    return result
    
    return None

def get_subtree(id: int, context_id: Optional[str] = None) -> Union[Dict[str, Any], Dict[str, str]]:
    """
    Get a specific todo and all its subtasks by ID.
    
    Args:
        id: The ID of the todo to retrieve
        context_id: If provided, only search in this context
        
    Returns:
        The todo subtree or an error message
    """
    if context_id:
        err = get_context_or_error(context_id)
        if err:
            return err
        todo = get_todo_or_error(todos_by_context[context_id], id, context_id)
        if isinstance(todo, dict):
            return todo
    else:
        context_id = find_todo_context(id)
        if not context_id:
            return error_dict(f"Todo with ID {id} not found in any context")
        todo = get_todo_or_error(todos_by_context[context_id], id, context_id)
        if isinstance(todo, dict):
            return todo
    return deepcopy(tree_to_dict(todo))

def update_subtree(id: int, title: Optional[str] = None, description: Optional[str] = None, 
                  deadline: Optional[str] = None, completed: Optional[bool] = None,
                  how_to_guide: Optional[str] = None, context_id: Optional[str] = None) -> Union[Dict[str, Any], Dict[str, str]]:
    """
    Update a todo's properties while preserving its subtasks.
    
    The description should be short and to the point. Use how_to_guide for detailed, step-by-step instructions or explanations in markdown format.
    
    Args:
        id: The ID of the todo to update
        title: New title (if provided)
        description: Short summary (keep it brief)
        deadline: New deadline (if provided)
        completed: New completed status (if provided)
        how_to_guide: New how-to guide in markdown (use for detailed instructions)
        context_id: If provided, only search in this context
        
    Returns:
        The updated todo or an error message
    """
    if context_id:
        err = get_context_or_error(context_id)
        if err:
            return err
        todo = get_todo_or_error(todos_by_context[context_id], id, context_id)
        if isinstance(todo, dict):
            return todo
    else:
        context_id = find_todo_context(id)
        if not context_id:
            return error_dict(f"Todo with ID {id} not found in any context")
        todo = get_todo_or_error(todos_by_context[context_id], id, context_id)
        if isinstance(todo, dict):
            return todo
    if title is not None:
        todo.title = title
    if description is not None:
        todo.description = description
    if deadline is not None:
        todo.deadline = deadline
    if completed is not None:
        todo.completed = completed
    if how_to_guide is not None:
        todo.how_to_guide = how_to_guide
    save_todos()
    return tree_to_dict(todo)

def find_parent_of_todo(todo_list: List[Node], id: int) -> Optional[Node]:
    """Find the parent of a todo by the todo's ID using anytree's .parent attribute."""
    node = find_todo(todo_list, id)
    return node.parent if node else None

def move_subtree(id: int, new_parent_id: Optional[int] = None, 
                source_context_id: Optional[str] = None, target_context_id: Optional[str] = None) -> Union[Dict[str, Any], Dict[str, str]]:
    """
    Move a todo and all its subtasks to a new parent or to the root level,
    optionally moving between contexts.
    
    Args:
        id: The ID of the todo subtree to move
        new_parent_id: The ID of the new parent todo, or None to move to root level
        source_context_id: If provided, only search in this context for the todo to move
        target_context_id: If provided, move the todo to this context
        
    Returns:
        The moved subtree or an error message
    """
    if source_context_id:
        err = get_context_or_error(source_context_id)
        if err:
            return err
    else:
        source_context_id = find_todo_context(id)
        if not source_context_id:
            return error_dict(f"Todo with ID {id} not found in any context")
    if target_context_id is None:
        target_context_id = source_context_id
    elif target_context_id not in todos_by_context:
        return error_dict(f"Target context with ID {target_context_id} not found")
    if new_parent_id == id:
        return error_dict("Cannot move a todo to be its own child")
    todo_to_move = get_todo_or_error(todos_by_context[source_context_id], id, source_context_id)
    if isinstance(todo_to_move, dict):
        return todo_to_move
    if new_parent_id is not None:
        new_parent = get_todo_or_error(todos_by_context[target_context_id], new_parent_id, target_context_id)
        if isinstance(new_parent, dict):
            return new_parent
        if source_context_id == target_context_id:
            current = new_parent
            while current:
                parent = find_parent_of_todo(todos_by_context[source_context_id], current.id)
                if parent and parent.id == id:
                    return error_dict("Cannot move a todo to be a child of its own descendant")
                current = parent
    current_parent = find_parent_of_todo(todos_by_context[source_context_id], id)
    todo_copy = deepcopy(todo_to_move)
    if current_parent:
        current_parent.children = [st for st in current_parent.children if st.id != id]
    else:
        todos_by_context[source_context_id] = [t for t in todos_by_context[source_context_id] if t.id != id]
    if new_parent_id is None:
        todos_by_context[target_context_id].append(todo_copy)
    else:
        todo_copy.parent = new_parent
    save_todos()
    return tree_to_dict(todo_copy)

def get_todos(context_id: str = default_context_id) -> List[Dict[str, Any]]:
    """
    Get all todos from a specific context.
    
    Args:
        context_id: The context to get todos from
        
    Returns:
        List of todos in the context or empty list if context not found
    """
    if context_id not in todos_by_context:
        return []
    return [tree_to_dict(todo) for todo in todos_by_context[context_id]]

# --- Simplification Helpers ---
def error_dict(msg: str) -> Dict[str, str]:
    return {"error": msg}

def get_context_or_error(context_id: str) -> Optional[Dict[str, Any]]:
    if context_id not in todos_by_context:
        return error_dict(f"Context with ID {context_id} not found")
    return None

def get_todo_or_error(todo_list: List[Node], id: int, context_id: str) -> Union[Node, Dict[str, str]]:
    todo = find_todo(todo_list, id)
    if not todo:
        return error_dict(f"Todo with ID {id} not found in context {context_id}")
    return todo

# Load todos on import
load_todos()
