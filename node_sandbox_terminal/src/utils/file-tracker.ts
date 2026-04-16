import { promises as fs } from "fs";
import path from "path";
import { glob } from "glob";
import { SandboxDiff, FileChange } from "../types/index.js";

export class FileTracker {
  constructor(
    private sourcePath: string,
    private sandboxPath: string
  ) {}

  async calculateDiff(): Promise<SandboxDiff> {
    const sourceFiles = await this.getFileMap(this.sourcePath);
    const sandboxFiles = await this.getFileMap(this.sandboxPath);

    const added: FileChange[] = [];
    const modified: FileChange[] = [];
    const deleted: FileChange[] = [];

    // Find added and modified files
    for (const [relPath, sandboxInfo] of sandboxFiles) {
      const sourceInfo = sourceFiles.get(relPath);
      
      if (!sourceInfo) {
        // File added in sandbox
        added.push({
          path: relPath,
          type: "added",
          size: sandboxInfo.size,
          permissions: sandboxInfo.permissions,
        });
      } else if (sandboxInfo.mtime > sourceInfo.mtime || sandboxInfo.size !== sourceInfo.size) {
        // File modified in sandbox
        modified.push({
          path: relPath,
          type: "modified",
          size: sandboxInfo.size,
          permissions: sandboxInfo.permissions,
        });
      }
    }

    // Find deleted files
    for (const [relPath, sourceInfo] of sourceFiles) {
      if (!sandboxFiles.has(relPath)) {
        deleted.push({
          path: relPath,
          type: "deleted",
        });
      }
    }

    return { added, modified, deleted };
  }

  private async getFileMap(basePath: string): Promise<Map<string, {
    size: number;
    mtime: number;
    permissions: string;
  }>> {
    const fileMap = new Map();

    try {
      const files = await glob("**/*", {
        cwd: basePath,
        dot: true,
        nodir: true,
      });

      for (const file of files) {
        const fullPath = path.join(basePath, file);
        try {
          const stats = await fs.stat(fullPath);
          fileMap.set(file, {
            size: stats.size,
            mtime: stats.mtime.getTime(),
            permissions: (stats.mode & parseInt("777", 8)).toString(8),
          });
        } catch {
          // File might have been deleted during scan
        }
      }
    } catch {
      // Directory might not exist
    }

    return fileMap;
  }
}