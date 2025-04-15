# syntax=docker/dockerfile:1
FROM python:3.12-slim

# Install system dependencies for SQLite
RUN apt-get update && apt-get install -y libsqlite3-0 && rm -rf /var/lib/apt/lists/*

# Install uv (fast Python package manager)
RUN pip install --upgrade pip && pip install uv

# Set work directory
WORKDIR /app

# Copy project files
COPY . /app

# Install dependencies
RUN uv sync

# Default command to run the MCP server
CMD ["uv", "run", "--with", "mcp[cli]", "mcp", "run", "main.py"]
