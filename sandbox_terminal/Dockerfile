FROM python:3.12-slim

# Install Docker CLI (for Docker-in-Docker functionality) and uv
RUN apt-get update && apt-get install -y \
    docker.io \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --upgrade pip && pip install uv

# Set working directory
WORKDIR /app

# Copy project files
COPY . /app

# Install dependencies using uv (without mcp since we'll use the local version)
RUN uv sync

# Create directory for sandbox storage
RUN mkdir -p /tmp/mcp-sandboxes

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV SANDBOX_STORAGE_PATH=/tmp/mcp-sandboxes

# Run as non-root user (but with docker group for container management)
RUN useradd -m -s /bin/bash mcp && \
    usermod -aG docker mcp && \
    chown -R mcp:mcp /app /tmp/mcp-sandboxes

# Temporarily run as root to debug Docker socket permissions
# USER mcp

# Default command to run the MCP server with local MCP SDK
# The local MCP SDK path will be mounted at runtime
CMD ["uv", "run", "--with", "mcp[cli] @ /mcp-sdk", "mcp", "run", "main.py"]