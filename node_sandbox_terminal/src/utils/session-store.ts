import { promises as fs } from "fs";
import path from "path";
import * as fse from "fs-extra";
import { SandboxSession } from "../types/index.js";

export class SessionStore {
  constructor(private storagePath: string) {}

  async init(): Promise<void> {
    await fse.ensureDir(this.storagePath);
  }

  async saveSession(session: SandboxSession): Promise<void> {
    await this.init();
    const sessionPath = path.join(this.storagePath, `${session.name}.json`);
    
    // Convert dates to ISO strings for JSON serialization
    const serializable = {
      ...session,
      created: session.created.toISOString(),
      lastAccessed: session.lastAccessed.toISOString(),
      commandHistory: session.commandHistory.map(entry => ({
        ...entry,
        timestamp: entry.timestamp.toISOString(),
      })),
    };

    await fs.writeFile(sessionPath, JSON.stringify(serializable, null, 2));
  }

  async getSession(name: string): Promise<SandboxSession | null> {
    const sessionPath = path.join(this.storagePath, `${name}.json`);
    
    try {
      const data = await fs.readFile(sessionPath, "utf-8");
      const parsed = JSON.parse(data);
      
      // Convert ISO strings back to dates
      return {
        ...parsed,
        created: new Date(parsed.created),
        lastAccessed: new Date(parsed.lastAccessed),
        commandHistory: parsed.commandHistory.map((entry: any) => ({
          ...entry,
          timestamp: new Date(entry.timestamp),
        })),
      };
    } catch {
      return null;
    }
  }

  async listSessions(): Promise<SandboxSession[]> {
    await this.init();
    
    try {
      const files = await fs.readdir(this.storagePath);
      const sessions: SandboxSession[] = [];

      for (const file of files) {
        if (file.endsWith(".json")) {
          const name = file.slice(0, -5);
          const session = await this.getSession(name);
          if (session) {
            // Check for expired sessions (24 hours)
            const age = Date.now() - session.lastAccessed.getTime();
            if (age < 24 * 60 * 60 * 1000) {
              sessions.push(session);
            } else {
              // Clean up expired session
              await this.deleteSession(name);
            }
          }
        }
      }

      return sessions;
    } catch {
      return [];
    }
  }

  async deleteSession(name: string): Promise<void> {
    const sessionPath = path.join(this.storagePath, `${name}.json`);
    try {
      await fs.unlink(sessionPath);
    } catch {
      // Session might already be deleted
    }
  }
}