import { promises as fs } from "fs";
import path from "path";
import { v4 as uuidv4 } from "uuid";
import { glob } from "glob";
import { minimatch } from "minimatch";
import * as fse from "fs-extra";
import {
  SandboxSession,
  SandboxConfig,
  CommandResult,
  SandboxDiff,
  FileChange,
} from "../types/index.js";
import { DockerSandbox } from "./docker-sandbox.js";
import { CommandValidator } from "./command-validator.js";
import { FileTracker } from "./file-tracker.js";
import { SessionStore } from "./session-store.js";

export class SandboxManager {
  private config: SandboxConfig;
  private docker: DockerSandbox;
  private validator: CommandValidator;
  private sessionStore: SessionStore;

  constructor(config: SandboxConfig) {
    this.config = config;
    this.docker = new DockerSandbox(config);
    this.validator = new CommandValidator(config.security);
    this.sessionStore = new SessionStore(path.join(config.storagePath, "sessions"));
  }

  async createSandbox(
    sourcePath: string,
    sessionName: string,
    allowedPaths?: string[],
    excludePatterns?: string[]
  ): Promise<SandboxSession> {
    // Validate session name
    if (!/^[a-zA-Z0-9_-]+$/.test(sessionName)) {
      throw new Error("Session name must contain only letters, numbers, hyphens, and underscores");
    }

    // Check if session already exists
    const existing = await this.sessionStore.getSession(sessionName);
    if (existing) {
      throw new Error(`Session '${sessionName}' already exists`);
    }

    // Check concurrent limit
    const sessions = await this.sessionStore.listSessions();
    if (sessions.length >= this.config.maxConcurrent) {
      throw new Error(`Maximum concurrent sandboxes (${this.config.maxConcurrent}) reached`);
    }

    // Create sandbox directory
    const sandboxId = uuidv4();
    const sandboxPath = path.join(this.config.storagePath, "sandboxes", sandboxId);
    await fse.ensureDir(sandboxPath);

    try {
      // Copy source directory to sandbox
      await this.copyDirectory(sourcePath, sandboxPath, excludePatterns);

      // Create session
      const session: SandboxSession = {
        id: sandboxId,
        name: sessionName,
        source: sourcePath,
        sandboxPath,
        created: new Date(),
        lastAccessed: new Date(),
        workingDir: "/workspace",
        environment: {},
        commandHistory: [],
        allowedPaths,
        networkEnabled: this.config.security.networkEnabled,
      };

      // Create Docker container
      const containerId = await this.docker.createContainer(session);
      session.containerId = containerId;

      // Save session
      await this.sessionStore.saveSession(session);

      return session;
    } catch (error) {
      // Cleanup on failure
      await fse.remove(sandboxPath);
      throw error;
    }
  }

  async listSandboxes(): Promise<Array<{
    name: string;
    source: string;
    created: string;
    size: string;
    active: boolean;
  }>> {
    const sessions = await this.sessionStore.listSessions();
    const results = [];

    for (const session of sessions) {
      const size = await this.getDirectorySize(session.sandboxPath);
      const active = session.containerId ? await this.docker.isContainerRunning(session.containerId) : false;
      
      results.push({
        name: session.name,
        source: session.source,
        created: session.created.toISOString(),
        size: this.formatBytes(size),
        active,
      });
    }

    return results;
  }

  async executeCommand(
    sessionName: string,
    command: string,
    workingDir?: string,
    timeout?: number
  ): Promise<CommandResult> {
    const session = await this.getSession(sessionName);

    // Validate command
    if (!this.validator.isCommandSafe(command)) {
      throw new Error("Command blocked for security reasons");
    }

    // Update session
    session.lastAccessed = new Date();
    if (workingDir) {
      session.workingDir = path.join("/workspace", workingDir);
    }

    // Execute in container
    const result = await this.docker.executeCommand(
      session,
      command,
      timeout || this.config.defaultTimeout
    );

    // Update command history
    session.commandHistory.push({
      command,
      exitCode: result.exitCode,
      output: result.stdout,
      error: result.stderr,
      timestamp: new Date(),
      workingDir: session.workingDir,
    });

    // Limit history size
    if (session.commandHistory.length > 100) {
      session.commandHistory = session.commandHistory.slice(-100);
    }

    await this.sessionStore.saveSession(session);

    return result;
  }

  async readFile(sessionName: string, filePath: string): Promise<string> {
    const session = await this.getSession(sessionName);
    const fullPath = path.join(session.sandboxPath, filePath);

    // Validate path is within sandbox
    if (!this.isPathInSandbox(fullPath, session.sandboxPath)) {
      throw new Error("Access denied: path outside sandbox");
    }

    return await fs.readFile(fullPath, "utf-8");
  }

  async writeFile(sessionName: string, filePath: string, content: string): Promise<void> {
    const session = await this.getSession(sessionName);
    const fullPath = path.join(session.sandboxPath, filePath);

    // Validate path is within sandbox
    if (!this.isPathInSandbox(fullPath, session.sandboxPath)) {
      throw new Error("Access denied: path outside sandbox");
    }

    // Ensure directory exists
    await fse.ensureDir(path.dirname(fullPath));
    
    // Write file
    await fs.writeFile(fullPath, content);

    // Update session
    session.lastAccessed = new Date();
    await this.sessionStore.saveSession(session);
  }

  async listFiles(sessionName: string, dirPath: string): Promise<Array<{
    name: string;
    type: "file" | "directory";
    size: number;
    modified: string;
  }>> {
    const session = await this.getSession(sessionName);
    const fullPath = path.join(session.sandboxPath, dirPath);

    // Validate path is within sandbox
    if (!this.isPathInSandbox(fullPath, session.sandboxPath)) {
      throw new Error("Access denied: path outside sandbox");
    }

    const entries = await fs.readdir(fullPath, { withFileTypes: true });
    const results = [];

    for (const entry of entries) {
      const entryPath = path.join(fullPath, entry.name);
      const stats = await fs.stat(entryPath);

      results.push({
        name: entry.name,
        type: entry.isDirectory() ? "directory" as const : "file" as const,
        size: stats.size,
        modified: stats.mtime.toISOString(),
      });
    }

    return results.sort((a, b) => {
      if (a.type !== b.type) {
        return a.type === "directory" ? -1 : 1;
      }
      return a.name.localeCompare(b.name);
    });
  }

  async getDiff(sessionName: string): Promise<SandboxDiff> {
    const session = await this.getSession(sessionName);
    const tracker = new FileTracker(session.source, session.sandboxPath);
    return await tracker.calculateDiff();
  }

  async resetSandbox(sessionName: string): Promise<void> {
    const session = await this.getSession(sessionName);

    // Remove sandbox directory
    await fse.remove(session.sandboxPath);

    // Recreate from source
    await fse.ensureDir(session.sandboxPath);
    await this.copyDirectory(session.source, session.sandboxPath);

    // Restart container
    if (session.containerId) {
      await this.docker.removeContainer(session.containerId);
      session.containerId = await this.docker.createContainer(session);
    }

    // Reset session state
    session.commandHistory = [];
    session.workingDir = "/workspace";
    session.lastAccessed = new Date();

    await this.sessionStore.saveSession(session);
  }

  async destroySandbox(sessionName: string): Promise<void> {
    const session = await this.getSession(sessionName);

    // Remove container
    if (session.containerId) {
      await this.docker.removeContainer(session.containerId);
    }

    // Remove sandbox directory
    await fse.remove(session.sandboxPath);

    // Remove session
    await this.sessionStore.deleteSession(sessionName);
  }

  async commitChanges(
    sessionName: string,
    targetPath: string,
    previewOnly = false
  ): Promise<SandboxDiff | { committed: boolean; diff: SandboxDiff }> {
    const session = await this.getSession(sessionName);
    const diff = await this.getDiff(sessionName);

    if (previewOnly) {
      return diff;
    }

    // Apply changes
    for (const file of diff.deleted) {
      const targetFile = path.join(targetPath, file.path);
      if (await fse.pathExists(targetFile)) {
        await fse.remove(targetFile);
      }
    }

    for (const file of [...diff.added, ...diff.modified]) {
      const sourceFile = path.join(session.sandboxPath, file.path);
      const targetFile = path.join(targetPath, file.path);
      await fse.ensureDir(path.dirname(targetFile));
      await fse.copy(sourceFile, targetFile, { overwrite: true });
    }

    return { committed: true, diff };
  }

  private async getSession(sessionName: string): Promise<SandboxSession> {
    const session = await this.sessionStore.getSession(sessionName);
    if (!session) {
      throw new Error(`Session '${sessionName}' not found`);
    }
    return session;
  }

  private async copyDirectory(
    source: string,
    destination: string,
    excludePatterns?: string[]
  ): Promise<void> {
    const files = await glob("**/*", {
      cwd: source,
      dot: true,
      nodir: true,
    });

    for (const file of files) {
      // Check exclude patterns
      if (excludePatterns?.some(pattern => minimatch(file, pattern))) {
        continue;
      }

      const sourcePath = path.join(source, file);
      const destPath = path.join(destination, file);

      await fse.ensureDir(path.dirname(destPath));
      await fse.copy(sourcePath, destPath);
    }
  }

  private isPathInSandbox(testPath: string, sandboxPath: string): boolean {
    const relative = path.relative(sandboxPath, testPath);
    return !relative.startsWith("..") && !path.isAbsolute(relative);
  }

  private async getDirectorySize(dirPath: string): Promise<number> {
    let size = 0;
    const files = await glob("**/*", {
      cwd: dirPath,
      dot: true,
      nodir: true,
    });

    for (const file of files) {
      const filePath = path.join(dirPath, file);
      const stats = await fs.stat(filePath);
      size += stats.size;
    }

    return size;
  }

  private formatBytes(bytes: number): string {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
  }
}