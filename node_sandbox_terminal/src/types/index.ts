export interface SandboxSession {
  id: string;
  name: string;
  source: string;
  sandboxPath: string;
  containerId?: string;
  created: Date;
  lastAccessed: Date;
  workingDir: string;
  environment: Record<string, string>;
  commandHistory: CommandHistoryEntry[];
  allowedPaths?: string[];
  networkEnabled: boolean;
}

export interface CommandHistoryEntry {
  command: string;
  exitCode: number;
  output: string;
  error?: string;
  timestamp: Date;
  workingDir: string;
}

export interface SandboxConfig {
  maxConcurrent: number;
  defaultTimeout: number;
  maxSizeMb: number;
  storagePath: string;
  resourceLimits: ResourceLimits;
  security: SecurityConfig;
}

export interface ResourceLimits {
  memory: string;
  cpuQuota: number;
  pidsLimit: number;
}

export interface SecurityConfig {
  networkEnabled: boolean;
  readonlyPaths: string[];
  blockedCommands: string[];
  allowedPaths?: string[];
}

export interface FileChange {
  path: string;
  type: 'added' | 'modified' | 'deleted';
  size?: number;
  permissions?: string;
}

export interface SandboxDiff {
  added: FileChange[];
  modified: FileChange[];
  deleted: FileChange[];
}

export interface CommandResult {
  exitCode: number;
  stdout: string;
  stderr: string;
  timedOut: boolean;
}