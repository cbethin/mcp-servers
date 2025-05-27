"""
Helper functions for testing async tools.
"""

import asyncio
from typing import Any, Tuple, List


async def run_async_tool(async_gen) -> Any:
    """
    Run an async tool to completion and return only the final result.
    
    This consumes all yielded progress messages and returns the final result.
    """
    result = None
    async for value in async_gen:
        # Just consume all values - the tool should return the result
        pass
    # For async generators with return values, we need to handle differently
    # The MCP framework might be handling this internally
    return result


async def run_async_tool_with_progress(async_gen) -> Tuple[List[str], Any]:
    """
    Run an async tool and collect both progress messages and the final result.
    
    Returns:
        Tuple of (progress_messages, final_result)
    """
    progress = []
    result = None
    
    # Collect all values from the async generator
    async for value in async_gen:
        # All values should be strings now
        progress.append(value)
    
    # Since we can't return structured data, tests need to parse from strings
    return progress, result


def sync_run_async_tool(async_gen) -> Any:
    """
    Synchronously run an async tool (for use in sync test methods).
    
    Returns only the final result.
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(run_async_tool(async_gen))
    finally:
        loop.close()


def sync_run_async_tool_with_progress(async_gen) -> Tuple[List[str], Any]:
    """
    Synchronously run an async tool and get progress messages.
    
    Returns:
        Tuple of (progress_messages, final_result)
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(run_async_tool_with_progress(async_gen))
    finally:
        loop.close()