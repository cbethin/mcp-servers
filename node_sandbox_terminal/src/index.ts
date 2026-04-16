#!/usr/bin/env node
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  Tool,
} from "@modelcontextprotocol/sdk/types.js";
import { SandboxManager } from "./utils/sandbox-manager.js";
import { z } from "zod";

const DEFAULT_CONFIG = {
  maxConcurrent: parseInt(process.env.MAX_SANDBOXES || "10"),
  defaultTimeout: parseInt(process.env.COMMAND_TIMEOUT || "30"),
  maxSizeMb: parseInt(process.env.MAX_SANDBOX_SIZE || "1000"),
  storagePath: process.env.SANDBOX_STORAGE_PATH || "/tmp/node-mcp-sandboxes",
  resourceLimits: {
    memory: process.env.SANDBOX_MEMORY || "1g",
    cpuQuota: parseInt(process.env.SANDBOX_CPU_QUOTA || "50"),
    pidsLimit: parseInt(process.env.SANDBOX_PIDS_LIMIT || "100"),
  },
  security: {
    networkEnabled: process.env.SANDBOX_NETWORK_ENABLED === "true",
    readonlyPaths: ["/etc", "/sys", "/proc"],
    blockedCommands: [
      "shutdown", "reboot", "init", "systemctl",
      "rm -rf /", "rm -rf /*", ":(){ :|:& };:",
      "dd if=/dev/zero", "mkfs", "fdisk"
    ],
    allowedPaths: process.env.SANDBOX_ALLOWED_PATHS?.split(",") || undefined,
  },
};

const sandboxManager = new SandboxManager(DEFAULT_CONFIG);

const TOOLS: Tool[] = [
  {
    name: "sandbox_create",
    description: "Create a new sandbox session from a source directory with optional folder access restrictions",
    inputSchema: {
      type: "object",
      properties: {
        source_path: {
          type: "string",
          description: "Path to the source directory to sandbox",
        },
        session_name: {
          type: "string",
          description: "Unique name for this sandbox session",
        },
        allowed_paths: {
          type: "array",
          items: { type: "string" },
          description: "Additional paths the sandbox can access (beyond the source directory)",
        },
        exclude_patterns: {
          type: "array",
          items: { type: "string" },
          description: "Glob patterns for files/directories to exclude from the sandbox",
        },
      },
      required: ["source_path", "session_name"],
    },
  },
  {
    name: "sandbox_list",
    description: "List all active sandbox sessions",
    inputSchema: {
      type: "object",
      properties: {},
    },
  },
  {
    name: "sandbox_execute",
    description: "Execute a command within a sandbox session",
    inputSchema: {
      type: "object",
      properties: {
        session_name: {
          type: "string",
          description: "Name of the sandbox session",
        },
        command: {
          type: "string",
          description: "Command to execute",
        },
        working_dir: {
          type: "string",
          description: "Working directory within the sandbox (relative to sandbox root)",
        },
        timeout: {
          type: "number",
          description: "Timeout in seconds (default: 30)",
        },
      },
      required: ["session_name", "command"],
    },
  },
  {
    name: "sandbox_read_file",
    description: "Read a file from within a sandbox",
    inputSchema: {
      type: "object",
      properties: {
        session_name: {
          type: "string",
          description: "Name of the sandbox session",
        },
        file_path: {
          type: "string",
          description: "Path to the file within the sandbox",
        },
      },
      required: ["session_name", "file_path"],
    },
  },
  {
    name: "sandbox_write_file",
    description: "Write or modify a file within a sandbox",
    inputSchema: {
      type: "object",
      properties: {
        session_name: {
          type: "string",
          description: "Name of the sandbox session",
        },
        file_path: {
          type: "string",
          description: "Path to the file within the sandbox",
        },
        content: {
          type: "string",
          description: "Content to write to the file",
        },
      },
      required: ["session_name", "file_path", "content"],
    },
  },
  {
    name: "sandbox_list_files",
    description: "List files and directories within a sandbox",
    inputSchema: {
      type: "object",
      properties: {
        session_name: {
          type: "string",
          description: "Name of the sandbox session",
        },
        path: {
          type: "string",
          description: "Path within the sandbox to list (default: /)",
        },
      },
      required: ["session_name"],
    },
  },
  {
    name: "sandbox_diff",
    description: "Show all changes made within a sandbox compared to the original",
    inputSchema: {
      type: "object",
      properties: {
        session_name: {
          type: "string",
          description: "Name of the sandbox session",
        },
      },
      required: ["session_name"],
    },
  },
  {
    name: "sandbox_reset",
    description: "Reset a sandbox to its original state",
    inputSchema: {
      type: "object",
      properties: {
        session_name: {
          type: "string",
          description: "Name of the sandbox session",
        },
      },
      required: ["session_name"],
    },
  },
  {
    name: "sandbox_destroy",
    description: "Remove a sandbox session and free resources",
    inputSchema: {
      type: "object",
      properties: {
        session_name: {
          type: "string",
          description: "Name of the sandbox session",
        },
      },
      required: ["session_name"],
    },
  },
  {
    name: "sandbox_commit",
    description: "Apply sandbox changes back to a target directory",
    inputSchema: {
      type: "object",
      properties: {
        session_name: {
          type: "string",
          description: "Name of the sandbox session",
        },
        target_path: {
          type: "string",
          description: "Path to apply changes to",
        },
        preview_only: {
          type: "boolean",
          description: "Only preview changes without applying them",
        },
      },
      required: ["session_name", "target_path"],
    },
  },
];

async function main() {
  const server = new Server(
    {
      name: "node-sandbox-terminal",
      version: "1.0.0",
    },
    {
      capabilities: {
        tools: {},
      },
    }
  );

  server.setRequestHandler(ListToolsRequestSchema, async () => ({
    tools: TOOLS,
  }));

  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params;

    try {
      switch (name) {
        case "sandbox_create": {
          const { source_path, session_name, allowed_paths, exclude_patterns } = args as any;
          const result = await sandboxManager.createSandbox(
            source_path,
            session_name,
            allowed_paths,
            exclude_patterns
          );
          return {
            content: [{
              type: "text",
              text: JSON.stringify(result, null, 2),
            }],
          };
        }

        case "sandbox_list": {
          const sessions = await sandboxManager.listSandboxes();
          return {
            content: [{
              type: "text",
              text: JSON.stringify(sessions, null, 2),
            }],
          };
        }

        case "sandbox_execute": {
          const { session_name, command, working_dir, timeout } = args as any;
          const result = await sandboxManager.executeCommand(
            session_name,
            command,
            working_dir,
            timeout
          );
          return {
            content: [{
              type: "text",
              text: JSON.stringify(result, null, 2),
            }],
          };
        }

        case "sandbox_read_file": {
          const { session_name, file_path } = args as any;
          const content = await sandboxManager.readFile(session_name, file_path);
          return {
            content: [{
              type: "text",
              text: content,
            }],
          };
        }

        case "sandbox_write_file": {
          const { session_name, file_path, content } = args as any;
          await sandboxManager.writeFile(session_name, file_path, content);
          return {
            content: [{
              type: "text",
              text: `File written successfully: ${file_path}`,
            }],
          };
        }

        case "sandbox_list_files": {
          const { session_name, path } = args as any;
          const files = await sandboxManager.listFiles(session_name, path || "/");
          return {
            content: [{
              type: "text",
              text: JSON.stringify(files, null, 2),
            }],
          };
        }

        case "sandbox_diff": {
          const { session_name } = args as any;
          const diff = await sandboxManager.getDiff(session_name);
          return {
            content: [{
              type: "text",
              text: JSON.stringify(diff, null, 2),
            }],
          };
        }

        case "sandbox_reset": {
          const { session_name } = args as any;
          await sandboxManager.resetSandbox(session_name);
          return {
            content: [{
              type: "text",
              text: `Sandbox '${session_name}' has been reset to its original state`,
            }],
          };
        }

        case "sandbox_destroy": {
          const { session_name } = args as any;
          await sandboxManager.destroySandbox(session_name);
          return {
            content: [{
              type: "text",
              text: `Sandbox '${session_name}' has been destroyed`,
            }],
          };
        }

        case "sandbox_commit": {
          const { session_name, target_path, preview_only } = args as any;
          const result = await sandboxManager.commitChanges(
            session_name,
            target_path,
            preview_only
          );
          return {
            content: [{
              type: "text",
              text: JSON.stringify(result, null, 2),
            }],
          };
        }

        default:
          throw new Error(`Unknown tool: ${name}`);
      }
    } catch (error) {
      return {
        content: [{
          type: "text",
          text: `Error: ${error instanceof Error ? error.message : String(error)}`,
        }],
        isError: true,
      };
    }
  });

  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("Node Sandbox Terminal MCP server running on stdio");
}

main().catch((error) => {
  console.error("Fatal error:", error);
  process.exit(1);
});