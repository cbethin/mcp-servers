import Docker from "dockerode";
import { Readable } from "stream";
import { SandboxSession, SandboxConfig, CommandResult } from "../types/index.js";

export class DockerSandbox {
  private docker: Docker;
  private config: SandboxConfig;
  private readonly imageName = "node-sandbox-terminal:latest";

  constructor(config: SandboxConfig) {
    this.docker = new Docker();
    this.config = config;
  }

  async ensureImage(): Promise<void> {
    try {
      await this.docker.getImage(this.imageName).inspect();
    } catch (error) {
      // Image doesn't exist, create it
      await this.buildImage();
    }
  }

  private async buildImage(): Promise<void> {
    const dockerfile = `
FROM ubuntu:22.04

# Install basic tools and Node.js
RUN apt-get update && apt-get install -y \\
    curl \\
    git \\
    build-essential \\
    python3 \\
    python3-pip \\
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \\
    && apt-get install -y nodejs \\
    && apt-get clean \\
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -s /bin/bash sandbox

# Set working directory
WORKDIR /workspace

# Switch to non-root user
USER sandbox

CMD ["/bin/bash"]
`;

    const stream = await this.docker.buildImage(
      {
        context: Buffer.from(dockerfile),
        src: ["Dockerfile"],
      },
      { t: this.imageName }
    );

    // Wait for build to complete
    await new Promise((resolve, reject) => {
      this.docker.modem.followProgress(stream, (err: any, res: any) =>
        err ? reject(err) : resolve(res)
      );
    });
  }

  async createContainer(session: SandboxSession): Promise<string> {
    await this.ensureImage();

    const binds = [`${session.sandboxPath}:/workspace`];
    
    // Add allowed paths if specified
    if (session.allowedPaths) {
      session.allowedPaths.forEach((path, index) => {
        binds.push(`${path}:/allowed${index}:ro`);
      });
    }

    const container = await this.docker.createContainer({
      Image: this.imageName,
      name: `sandbox-${session.id}`,
      WorkingDir: session.workingDir,
      Env: Object.entries(session.environment).map(([k, v]) => `${k}=${v}`),
      HostConfig: {
        Binds: binds,
        Memory: this.parseMemoryLimit(this.config.resourceLimits.memory),
        CpuQuota: this.config.resourceLimits.cpuQuota * 1000,
        PidsLimit: this.config.resourceLimits.pidsLimit,
        ReadonlyPaths: this.config.security.readonlyPaths,
        NetworkMode: session.networkEnabled ? "bridge" : "none",
        AutoRemove: false,
      },
      AttachStdin: false,
      AttachStdout: false,
      AttachStderr: false,
      Tty: false,
      OpenStdin: false,
    });

    await container.start();
    return container.id;
  }

  async executeCommand(
    session: SandboxSession,
    command: string,
    timeout: number
  ): Promise<CommandResult> {
    if (!session.containerId) {
      throw new Error("No container associated with session");
    }

    const container = this.docker.getContainer(session.containerId);

    try {
      const exec = await container.exec({
        Cmd: ["/bin/bash", "-c", command],
        WorkingDir: session.workingDir,
        Env: Object.entries(session.environment).map(([k, v]) => `${k}=${v}`),
        AttachStdout: true,
        AttachStderr: true,
      });

      const stream = await exec.start({ hijack: true, stdin: false });

      return new Promise((resolve, reject) => {
        let stdout = "";
        let stderr = "";
        let timedOut = false;

        const timeoutId = setTimeout(() => {
          timedOut = true;
          stream.destroy();
          resolve({
            exitCode: -1,
            stdout,
            stderr: stderr + "\nCommand timed out",
            timedOut: true,
          });
        }, timeout * 1000);

        stream.on("data", (chunk: Buffer) => {
          const data = chunk.toString();
          // Docker multiplexes stdout/stderr
          if (chunk[0] === 1) {
            stdout += data.slice(8);
          } else if (chunk[0] === 2) {
            stderr += data.slice(8);
          }
        });

        stream.on("end", async () => {
          clearTimeout(timeoutId);
          if (!timedOut) {
            const info = await exec.inspect();
            resolve({
              exitCode: info.ExitCode || 0,
              stdout,
              stderr,
              timedOut: false,
            });
          }
        });

        stream.on("error", (error: Error) => {
          clearTimeout(timeoutId);
          reject(error);
        });
      });
    } catch (error) {
      if (error instanceof Error && error.message.includes("not running")) {
        // Container stopped, restart it
        await container.start();
        return this.executeCommand(session, command, timeout);
      }
      throw error;
    }
  }

  async isContainerRunning(containerId: string): Promise<boolean> {
    try {
      const container = this.docker.getContainer(containerId);
      const info = await container.inspect();
      return info.State.Running;
    } catch {
      return false;
    }
  }

  async removeContainer(containerId: string): Promise<void> {
    try {
      const container = this.docker.getContainer(containerId);
      await container.stop({ t: 5 }).catch(() => {}); // Ignore if already stopped
      await container.remove();
    } catch {
      // Container might already be removed
    }
  }

  private parseMemoryLimit(limit: string): number {
    const units: { [key: string]: number } = {
      b: 1,
      k: 1024,
      m: 1024 * 1024,
      g: 1024 * 1024 * 1024,
    };

    const match = limit.toLowerCase().match(/^(\d+)([bkmg])?$/);
    if (!match) {
      throw new Error(`Invalid memory limit: ${limit}`);
    }

    const value = parseInt(match[1]);
    const unit = match[2] || "b";
    return value * units[unit];
  }
}