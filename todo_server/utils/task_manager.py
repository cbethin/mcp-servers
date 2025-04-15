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
tasks_by_context: Dict[str, List[Node]] = {}
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
    tasks = relationship('Task', back_populates='context', cascade="all, delete-orphan")

class Task(Base):
    __tablename__ = 'tasks'
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False)
    description = Column(Text, default="")
    deadline = Column(String)
    completed = Column(Boolean, default=False)
    created_at = Column(DateTime, nullable=False)
    how_to_guide = Column(Text, default="")
    context_id = Column(String, ForeignKey('contexts.id'), nullable=False)
    parent_id = Column(Integer, ForeignKey('tasks.id'), nullable=True)
    context = relationship('Context', back_populates='tasks')
    subtasks = relationship('Task', backref='parent', remote_side=[id], cascade="all, delete-orphan", single_parent=True)

# Create tables if they don't exist
Base.metadata.create_all(engine)

# --- AnyTree Conversion Helpers ---
def dict_to_tree(task_dict, parent=None):
    """Recursively convert a task dict (with subtasks) to an anytree Node tree."""
    node = Node(
        None,
        id=task_dict["id"],
        title=task_dict["title"],
        description=task_dict.get("description", ""),
        deadline=task_dict.get("deadline"),
        completed=task_dict.get("completed", False),
        created_at=task_dict.get("created_at"),
        how_to_guide=task_dict.get("how_to_guide", ""),
        parent=parent
    )
    for sub in task_dict.get("subtasks", []):
        dict_to_tree(sub, parent=node)
    return node

def tree_to_dict(node):
    """Recursively convert an anytree Node tree to a task dict (with subtasks)."""
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

def load_tasks():
    global tasks_by_context, contexts, next_id, default_context_id
    try:
        if os.path.exists("tasks.json"):
            with open("tasks.json", "r") as f:
                old_tasks = json.load(f)
            if isinstance(old_tasks, dict) and "contexts" in old_tasks:
                contexts = old_tasks["contexts"]
                # Convert dicts to Node trees
                tasks_by_context = {
                    ctx: [dict_to_tree(task) for task in task_list]
                    for ctx, task_list in old_tasks["tasks_by_context"].items()
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
                tasks_by_context = {default_context_id: [dict_to_tree(task) for task in old_tasks]}
            # Find the highest ID
            max_id = 0
            for context_tasks in tasks_by_context.values():
                for root in context_tasks:
                    for node in PreOrderIter(root):
                        max_id = max(max_id, getattr(node, "id", 0))
            next_id = max_id + 1
            save_tasks()
    except Exception as e:
        print(f"Error loading tasks: {e}")
        contexts = [{
            "id": default_context_id,
            "name": "Default",
            "description": "Default context",
            "created_at": datetime.now().isoformat()
        }]
        tasks_by_context = {default_context_id: []}
        next_id = 1

def get_max_id(task_list: List[Dict[str, Any]]) -> int:
    """Recursively find the highest ID in the task tree."""
    max_id = 0
    for task in task_list:
        max_id = max(max_id, task.get("id", 0))
        if "subtasks" in task and task["subtasks"]:
            subtask_max_id = get_max_id(task["subtasks"])
            max_id = max(max_id, subtask_max_id)
    return max_id

def save_tasks():
    try:
        with open("tasks.json", "w") as f:
            json.dump({
                "contexts": contexts,
                "tasks_by_context": {
                    ctx: [tree_to_dict(root) for root in task_list]
                    for ctx, task_list in tasks_by_context.items()
                }
            }, f)
    except Exception as e:
        print(f"Error saving tasks: {e}")

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
    Delete a context and all its tasks.
    
    Args:
        context_id: The ID of the context to delete
        
    Returns:
        Success or error message
    """
    global contexts, tasks_by_context
    
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
    
    # Remove the context and its tasks
    removed_context = contexts.pop(context_index)
    if context_id in tasks_by_context:
        del tasks_by_context[context_id]
    
    save_tasks()
    return {"success": True, "message": f"Context '{removed_context['name']}' deleted"}

def add_task(title: str, description: str = "", deadline: str = None, parent_id: int = None, context_id: str = default_context_id, how_to_guide: str = "") -> Dict[str, Any]:
    """
    Add a new task, either as a root task or as a subtask of another task, using SQLAlchemy.
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
        parent = session.query(Task).filter_by(id=parent_id, context_id=context_id).first()
        if not parent:
            session.close()
            return {"error": f"Parent task with ID {parent_id} not found in context {context_id}"}
    new_task = Task(
        title=title,
        description=description or "",
        deadline=deadline,
        completed=False,
        created_at=now,
        how_to_guide=how_to_guide or "",
        context_id=context_id,
        parent_id=parent_id
    )
    session.add(new_task)
    session.commit()
    session.refresh(new_task)
    task_dict = task_to_dict(new_task, session)
    session.close()
    return task_dict

def get_tasks(context_id: str = default_context_id) -> List[Dict[str, Any]]:
    """
    Get all root tasks from a specific context using SQLAlchemy.
    """
    session = SessionLocal()
    tasks = session.query(Task).filter_by(context_id=context_id, parent_id=None).all()
    result = [task_to_dict(task, session) for task in tasks]
    session.close()
    return result

def task_to_dict(task, session):
    """
    Recursively convert a Task SQLAlchemy object to a dict with subtasks.
    """
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "deadline": task.deadline,
        "completed": task.completed,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "how_to_guide": task.how_to_guide,
        "subtasks": [task_to_dict(sub, session) for sub in session.query(Task).filter_by(parent_id=task.id).all()]
    }

def update_subtree(id: int, title: Optional[str] = None, description: Optional[str] = None, 
                  deadline: Optional[str] = None, completed: Optional[bool] = None,
                  how_to_guide: Optional[str] = None, context_id: Optional[str] = None) -> Union[Dict[str, Any], Dict[str, str]]:
    """
    Update a task's properties while preserving its subtasks, using SQLAlchemy.
    """
    session = SessionLocal()
    task = session.query(Task).filter_by(id=id).first()
    if not task:
        session.close()
        return {"error": f"Task with ID {id} not found"}
    if title is not None:
        task.title = title
    if description is not None:
        task.description = description
    if deadline is not None:
        task.deadline = deadline
    if completed is not None:
        task.completed = completed
    if how_to_guide is not None:
        task.how_to_guide = how_to_guide
    session.commit()
    task_dict = task_to_dict(task, session)
    session.close()
    return task_dict

def delete_task(id: int, context_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Delete a task by ID (and its subtasks via cascade) using SQLAlchemy.
    """
    session = SessionLocal()
    task = session.query(Task).filter_by(id=id).first()
    if not task:
        session.close()
        return {"error": f"Task with ID {id} not found"}
    session.delete(task)
    session.commit()
    session.close()
    return {"success": True, "message": f"Task '{task.title}' deleted"}

def move_subtree(id: int, new_parent_id: Optional[int] = None, 
                source_context_id: Optional[str] = None, target_context_id: Optional[str] = None) -> Union[Dict[str, Any], Dict[str, str]]:
    """
    Move a task and all its subtasks to a new parent or to the root level, optionally between contexts, using SQLAlchemy.
    """
    session = SessionLocal()
    task = session.query(Task).filter_by(id=id).first()
    if not task:
        session.close()
        return {"error": f"Task with ID {id} not found"}
    if new_parent_id == id:
        session.close()
        return {"error": "Cannot move a task to be its own child"}
    if target_context_id:
        context = session.query(Context).filter_by(id=target_context_id).first()
        if not context:
            session.close()
            return {"error": f"Target context with ID {target_context_id} not found"}
        task.context_id = target_context_id
    if new_parent_id:
        parent = session.query(Task).filter_by(id=new_parent_id).first()
        if not parent:
            session.close()
            return {"error": f"Parent task with ID {new_parent_id} not found"}
        # Prevent cycles
        def is_descendant(child_id, ancestor_id):
            if child_id == ancestor_id:
                return True
            child = session.query(Task).filter_by(id=child_id).first()
            if child and child.parent_id:
                return is_descendant(child.parent_id, ancestor_id)
            return False
        if is_descendant(new_parent_id, id):
            session.close()
            return {"error": "Cannot move a task to be a child of its own descendant"}
        task.parent_id = new_parent_id
    else:
        task.parent_id = None
    session.commit()
    task_dict = task_to_dict(task, session)
    session.close()
    return task_dict

def add_subtask(task_list: List[Node], parent_id: int, subtask: Node) -> bool:
    """Recursively search for a parent task and add the subtask to it."""
    for task in task_list:
        if task.id == parent_id:
            subtask.parent = task
            return True
        if task.children:
            if add_subtask(task.children, parent_id, subtask):
                return True
    return False

def find_task(task_list: List[Node], id: int) -> Optional[Node]:
    """Find a task by its ID using anytree's PreOrderIter for all roots."""
    for root in task_list:
        for node in PreOrderIter(root):
            if node.id == id:
                return node
    return None

def find_task_context(id: int) -> Optional[str]:
    """Find which context a task belongs to using anytree's PreOrderIter."""
    for context_id, tasks in tasks_by_context.items():
        for root in tasks:
            for node in PreOrderIter(root):
                if node.id == id:
                    return context_id
    return None

def toggle_task(id: int, recursive: bool = False, context_id: Optional[str] = None) -> Union[Dict[str, Any], Dict[str, str]]:
    """
    Toggle the completion status of a task. Optionally toggle all subtasks too.
    
    Args:
        id: The ID of the task to toggle
        recursive: If True, also toggle all subtasks
        context_id: If provided, only search in this context
        
    Returns:
        The modified task or an error message
    """
    if context_id:
        err = get_context_or_error(context_id)
        if err:
            return err
        task = get_task_or_error(tasks_by_context[context_id], id, context_id)
        if isinstance(task, dict):
            return task
    else:
        context_id = find_task_context(id)
        if not context_id:
            return error_dict(f"Task with ID {id} not found in any context")
        task = get_task_or_error(tasks_by_context[context_id], id, context_id)
        if isinstance(task, dict):
            return task
    task.completed = not task.completed
    if recursive and task.children:
        toggle_subtasks(task.children, task.completed)
    save_tasks()
    return tree_to_dict(task)

def toggle_subtasks(subtasks: List[Node], completed: bool):
    """Recursively toggle all subtasks using anytree's PreOrderIter."""
    for subtask in subtasks:
        for node in PreOrderIter(subtask):
            node.completed = completed

def get_subtree(id: int, context_id: Optional[str] = None) -> Union[Dict[str, Any], Dict[str, str]]:
    """
    Get a specific task and all its subtasks by ID.
    
    Args:
        id: The ID of the task to retrieve
        context_id: If provided, only search in this context
        
    Returns:
        The task subtree or an error message
    """
    if context_id:
        err = get_context_or_error(context_id)
        if err:
            return err
        task = get_task_or_error(tasks_by_context[context_id], id, context_id)
        if isinstance(task, dict):
            return task
    else:
        context_id = find_task_context(id)
        if not context_id:
            return error_dict(f"Task with ID {id} not found in any context")
        task = get_task_or_error(tasks_by_context[context_id], id, context_id)
        if isinstance(task, dict):
            return task
    return deepcopy(tree_to_dict(task))

def find_parent_of_task(task_list: List[Node], id: int) -> Optional[Node]:
    """Find the parent of a task by the task's ID using anytree's .parent attribute."""
    node = find_task(task_list, id)
    return node.parent if node else None

# --- Simplification Helpers ---
def error_dict(msg: str) -> Dict[str, str]:
    return {"error": msg}

def get_context_or_error(context_id: str) -> Optional[Dict[str, Any]]:
    if context_id not in tasks_by_context:
        return error_dict(f"Context with ID {context_id} not found")
    return None

def get_task_or_error(task_list: List[Node], id: int, context_id: str) -> Union[Node, Dict[str, str]]:
    task = find_task(task_list, id)
    if not task:
        return error_dict(f"Task with ID {id} not found in context {context_id}")
    return task

# Load tasks on import
load_tasks()
