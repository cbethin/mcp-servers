import json
import os
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
from copy import deepcopy
import uuid
from anytree import Node, PreOrderIter
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

# Global data structures
contexts: List[Dict[str, Any]] = []
todos_by_context: Dict[str, List[Node]] = {}
next_id = 1
default_context_id = "default"

# SQLAlchemy setup
Base = declarative_base()
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'db.sqlite3')
DB_URL = f'sqlite:///{os.path.abspath(DB_PATH)}'
engine = create_engine(DB_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine)

class Context(Base):
    __tablename__ = 'contexts'
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text, default="")
    created_at = Column(DateTime, nullable=False)
    todos = relationship('Todo', back_populates='context', cascade="all, delete-orphan")

class Todo(Base):
    __tablename__ = 'todos'
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False)
    description = Column(Text, default="")
    deadline = Column(String)
    completed = Column(Boolean, default=False)
    created_at = Column(DateTime, nullable=False)
    how_to_guide = Column(Text, default="")
    context_id = Column(String, ForeignKey('contexts.id'), nullable=False)
    parent_id = Column(Integer, ForeignKey('todos.id'), nullable=True)
    context = relationship('Context', back_populates='todos')
    subtasks = relationship('Todo', backref='parent', remote_side=[id], cascade="all, delete-orphan", single_parent=True)

# Create tables if they don't exist
Base.metadata.create_all(engine)

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
    Create a new context session using SQLAlchemy.
    """
    session = SessionLocal()
    context_id = str(uuid.uuid4())
    now = datetime.now()
    new_context = Context(
        id=context_id,
        name=name,
        description=description,
        created_at=now
    )
    session.add(new_context)
    session.commit()
    session.refresh(new_context)
    session.close()
    return {
        "id": new_context.id,
        "name": new_context.name,
        "description": new_context.description,
        "created_at": new_context.created_at.isoformat()
    }

def get_contexts() -> List[Dict[str, Any]]:
    """
    Get all available contexts from the database.
    """
    session = SessionLocal()
    contexts = session.query(Context).all()
    result = [
        {
            "id": c.id,
            "name": c.name,
            "description": c.description,
            "created_at": c.created_at.isoformat()
        }
        for c in contexts
    ]
    session.close()
    return result

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
    Add a new todo, either as a root todo or as a subtask of another todo, using SQLAlchemy.
    """
    session = SessionLocal()
    now = datetime.now()
    # Check context exists
    context = session.query(Context).filter_by(id=context_id).first()
    if not context:
        session.close()
        return {"error": f"Context with ID {context_id} not found"}
    # If parent_id is provided, check parent exists
    parent = None
    if parent_id is not None:
        parent = session.query(Todo).filter_by(id=parent_id, context_id=context_id).first()
        if not parent:
            session.close()
            return {"error": f"Parent todo with ID {parent_id} not found in context {context_id}"}
    new_todo = Todo(
        title=title,
        description=description or "",
        deadline=deadline,
        completed=False,
        created_at=now,
        how_to_guide=how_to_guide or "",
        context_id=context_id,
        parent_id=parent_id
    )
    session.add(new_todo)
    session.commit()
    session.refresh(new_todo)
    todo_dict = todo_to_dict(new_todo, session)
    session.close()
    return todo_dict

def get_todos(context_id: str = default_context_id) -> List[Dict[str, Any]]:
    """
    Get all root todos from a specific context using SQLAlchemy.
    """
    session = SessionLocal()
    todos = session.query(Todo).filter_by(context_id=context_id, parent_id=None).all()
    result = [todo_to_dict(todo, session) for todo in todos]
    session.close()
    return result

def todo_to_dict(todo, session):
    """
    Recursively convert a Todo SQLAlchemy object to a dict with subtasks.
    """
    return {
        "id": todo.id,
        "title": todo.title,
        "description": todo.description,
        "deadline": todo.deadline,
        "completed": todo.completed,
        "created_at": todo.created_at.isoformat() if todo.created_at else None,
        "how_to_guide": todo.how_to_guide,
        "subtasks": [todo_to_dict(sub, session) for sub in session.query(Todo).filter_by(parent_id=todo.id).all()]
    }

def update_subtree(id: int, title: Optional[str] = None, description: Optional[str] = None, 
                  deadline: Optional[str] = None, completed: Optional[bool] = None,
                  how_to_guide: Optional[str] = None, context_id: Optional[str] = None) -> Union[Dict[str, Any], Dict[str, str]]:
    """
    Update a todo's properties while preserving its subtasks, using SQLAlchemy.
    """
    session = SessionLocal()
    todo = session.query(Todo).filter_by(id=id).first()
    if not todo:
        session.close()
        return {"error": f"Todo with ID {id} not found"}
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
    session.commit()
    todo_dict = todo_to_dict(todo, session)
    session.close()
    return todo_dict

def delete_todo(id: int, context_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Delete a todo by ID (and its subtasks via cascade) using SQLAlchemy.
    """
    session = SessionLocal()
    todo = session.query(Todo).filter_by(id=id).first()
    if not todo:
        session.close()
        return {"error": f"Todo with ID {id} not found"}
    session.delete(todo)
    session.commit()
    session.close()
    return {"success": True, "message": f"Todo '{todo.title}' deleted"}

def move_subtree(id: int, new_parent_id: Optional[int] = None, 
                source_context_id: Optional[str] = None, target_context_id: Optional[str] = None) -> Union[Dict[str, Any], Dict[str, str]]:
    """
    Move a todo and all its subtasks to a new parent or to the root level, optionally between contexts, using SQLAlchemy.
    """
    session = SessionLocal()
    todo = session.query(Todo).filter_by(id=id).first()
    if not todo:
        session.close()
        return {"error": f"Todo with ID {id} not found"}
    if new_parent_id == id:
        session.close()
        return {"error": "Cannot move a todo to be its own child"}
    if target_context_id:
        context = session.query(Context).filter_by(id=target_context_id).first()
        if not context:
            session.close()
            return {"error": f"Target context with ID {target_context_id} not found"}
        todo.context_id = target_context_id
    if new_parent_id:
        parent = session.query(Todo).filter_by(id=new_parent_id).first()
        if not parent:
            session.close()
            return {"error": f"Parent todo with ID {new_parent_id} not found"}
        # Prevent cycles
        def is_descendant(child_id, ancestor_id):
            if child_id == ancestor_id:
                return True
            child = session.query(Todo).filter_by(id=child_id).first()
            if child and child.parent_id:
                return is_descendant(child.parent_id, ancestor_id)
            return False
        if is_descendant(new_parent_id, id):
            session.close()
            return {"error": "Cannot move a todo to be a child of its own descendant"}
        todo.parent_id = new_parent_id
    else:
        todo.parent_id = None
    session.commit()
    todo_dict = todo_to_dict(todo, session)
    session.close()
    return todo_dict

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

def find_parent_of_todo(todo_list: List[Node], id: int) -> Optional[Node]:
    """Find the parent of a todo by the todo's ID using anytree's .parent attribute."""
    node = find_todo(todo_list, id)
    return node.parent if node else None

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
