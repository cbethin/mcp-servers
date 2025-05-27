"""
Docker container management for sandbox isolation.
"""

import os
import time
import logging
from typing import Dict, Optional, Tuple, Any
from pathlib import Path

try:
    import docker
    from docker.models.containers import Container
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False
    Container = Any

logger = logging.getLogger("sandbox_terminal.docker_sandbox")


class DockerSandbox:
    """Manages Docker containers for sandbox isolation."""
    
    def __init__(self):
        if not DOCKER_AVAILABLE:
            raise RuntimeError("Docker Python package not installed. Run: pip install docker")
            
        try:
            self.client = docker.from_env()
            # Test connection
            self.client.ping()
        except Exception as e:
            raise RuntimeError(f"Failed to connect to Docker daemon: {e}")
            
        self.base_image = "ubuntu:22.04"
        self.resource_limits = {
            "mem_limit": os.environ.get("SANDBOX_MEMORY_LIMIT", "1g"),
            "cpu_period": 100000,
            "cpu_quota": 50000,  # 50% CPU
            "pids_limit": 100
        }
        
    def build_sandbox_image(self) -> str:
        """Build the base sandbox image if needed."""
        image_name = "mcp-sandbox-terminal:latest"
        
        # Check if image already exists
        try:
            self.client.images.get(image_name)
            logger.info(f"Using existing image: {image_name}")
            return image_name
        except docker.errors.ImageNotFound:
            pass
            
        logger.info("Building sandbox Docker image...")
        
        dockerfile = """
FROM ubuntu:22.04

# Avoid prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install essential tools in one layer to reduce build time
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv \
    nodejs npm \
    git curl wget \
    build-essential \
    vim nano \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user
RUN useradd -m -s /bin/bash sandbox

# Set up working directory
WORKDIR /workspace

# Switch to non-root user
USER sandbox

# Set default command
CMD ["/bin/bash"]
"""
        
        # Build the image
        try:
            image, logs = self.client.images.build(
                fileobj=dockerfile.encode(),
                tag=image_name,
                rm=True
            )
            
            for log in logs:
                if 'stream' in log:
                    logger.debug(log['stream'].strip())
                    
            logger.info(f"Successfully built image: {image_name}")
            return image_name
            
        except Exception as e:
            logger.error(f"Failed to build Docker image: {e}")
            raise
    
    def create_container(
        self, 
        session_id: str,
        workspace_path: str,
        environment: Optional[Dict[str, str]] = None
    ) -> Container:
        """Create a new Docker container for a sandbox session."""
        image_name = self.build_sandbox_image()
        
        container_name = f"mcp-sandbox-{session_id}"
        
        # Prepare environment variables
        env = environment or {}
        env.update({
            "SANDBOX_SESSION": session_id,
            "HOME": "/home/sandbox",
            "USER": "sandbox"
        })
        
        # Create container
        try:
            container = self.client.containers.create(
                image_name,
                name=container_name,
                volumes={
                    workspace_path: {
                        'bind': '/workspace',
                        'mode': 'rw'
                    }
                },
                working_dir="/workspace",
                environment=env,
                network_mode="none" if not self._is_network_enabled() else "bridge",
                stdin_open=True,
                tty=True,
                **self.resource_limits
            )
            
            logger.info(f"Created container '{container_name}' for session '{session_id}'")
            return container
            
        except docker.errors.APIError as e:
            logger.error(f"Failed to create container: {e}")
            raise
    
    def start_container(self, container: Container) -> None:
        """Start a container."""
        try:
            container.start()
            logger.info(f"Started container '{container.name}'")
        except Exception as e:
            logger.error(f"Failed to start container: {e}")
            raise
    
    def stop_container(self, container: Container, timeout: int = 10) -> None:
        """Stop a container."""
        try:
            container.stop(timeout=timeout)
            logger.info(f"Stopped container '{container.name}'")
        except Exception as e:
            logger.error(f"Failed to stop container: {e}")
            # Force kill if stop fails
            try:
                container.kill()
            except:
                pass
    
    def remove_container(self, container: Container) -> None:
        """Remove a container."""
        try:
            container.remove(force=True)
            logger.info(f"Removed container '{container.name}'")
        except Exception as e:
            logger.error(f"Failed to remove container: {e}")
    
    def execute_command(
        self,
        container: Container,
        command: str,
        working_dir: Optional[str] = None,
        environment: Optional[Dict[str, str]] = None,
        timeout: int = 30
    ) -> Tuple[str, int]:
        """Execute a command in a container."""
        # Ensure container is running
        if container.status != "running":
            container.start()
            time.sleep(0.5)  # Give it a moment to start
        
        # Prepare exec command
        exec_cmd = f"/bin/bash -c '{command}'"
        if working_dir:
            exec_cmd = f"cd {working_dir} && {exec_cmd}"
            
        start_time = time.time()
        
        try:
            # Create exec instance
            exec_instance = self.client.api.exec_create(
                container.id,
                exec_cmd,
                environment=environment,
                workdir=working_dir or "/workspace",
                user="sandbox"
            )
            
            # Start exec and collect output
            output_generator = self.client.api.exec_start(
                exec_instance['Id'],
                stream=True
            )
            
            output_lines = []
            for chunk in output_generator:
                if time.time() - start_time > timeout:
                    # Timeout - try to stop the exec
                    try:
                        self.client.api.exec_stop(exec_instance['Id'])
                    except:
                        pass
                    return "Command timed out", -1
                    
                if chunk:
                    output_lines.append(chunk.decode('utf-8', errors='replace'))
            
            # Get exit code
            exec_info = self.client.api.exec_inspect(exec_instance['Id'])
            exit_code = exec_info.get('ExitCode', 0)
            
            output = ''.join(output_lines)
            execution_time = time.time() - start_time
            
            logger.debug(f"Command executed in {execution_time:.2f}s with exit code {exit_code}")
            return output, exit_code
            
        except Exception as e:
            logger.error(f"Failed to execute command: {e}")
            return str(e), -1
    
    def get_container(self, session_id: str) -> Optional[Container]:
        """Get a container by session ID."""
        container_name = f"mcp-sandbox-{session_id}"
        try:
            return self.client.containers.get(container_name)
        except docker.errors.NotFound:
            return None
    
    def list_sandbox_containers(self) -> list:
        """List all sandbox containers."""
        try:
            return self.client.containers.list(
                all=True,
                filters={"name": "mcp-sandbox-"}
            )
        except Exception as e:
            logger.error(f"Failed to list containers: {e}")
            return []
    
    def cleanup_stopped_containers(self) -> int:
        """Remove all stopped sandbox containers."""
        removed_count = 0
        for container in self.list_sandbox_containers():
            if container.status in ["exited", "dead"]:
                try:
                    container.remove()
                    removed_count += 1
                except Exception as e:
                    logger.error(f"Failed to remove container {container.name}: {e}")
        return removed_count
    
    def _is_network_enabled(self) -> bool:
        """Check if network should be enabled for sandboxes."""
        return os.environ.get("SANDBOX_NETWORK_ENABLED", "false").lower() == "true"
    
    def copy_to_container(self, container: Container, src_path: str, dst_path: str) -> None:
        """Copy files to a container."""
        import tarfile
        import io
        
        # Create tar archive in memory
        tar_stream = io.BytesIO()
        with tarfile.open(fileobj=tar_stream, mode='w') as tar:
            tar.add(src_path, arcname=os.path.basename(src_path))
        
        tar_stream.seek(0)
        
        try:
            container.put_archive(
                path=dst_path,
                data=tar_stream.read()
            )
        except Exception as e:
            logger.error(f"Failed to copy to container: {e}")
            raise
    
    def copy_from_container(self, container: Container, src_path: str, dst_path: str) -> None:
        """Copy files from a container."""
        try:
            stream, stat = container.get_archive(src_path)
            
            # Extract tar archive
            import tarfile
            import io
            
            tar_data = b''.join(stream)
            tar_stream = io.BytesIO(tar_data)
            
            with tarfile.open(fileobj=tar_stream, mode='r') as tar:
                tar.extractall(path=dst_path)
                
        except Exception as e:
            logger.error(f"Failed to copy from container: {e}")
            raise