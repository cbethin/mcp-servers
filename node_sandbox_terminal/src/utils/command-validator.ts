import { SecurityConfig } from "../types/index.js";

export class CommandValidator {
  private securityConfig: SecurityConfig;
  private dangerousPatterns: RegExp[];

  constructor(securityConfig: SecurityConfig) {
    this.securityConfig = securityConfig;
    this.dangerousPatterns = [
      // Fork bombs
      /:\(\)\{.*\|.*&\s*\};:/,
      /:(){ :|:& };:/,
      
      // Resource exhaustion
      /dd\s+if=\/dev\/(zero|urandom)/,
      /yes\s*\|/,
      /cat\s+\/dev\/(zero|urandom)/,
      
      // System modification
      /mkfs/,
      /fdisk/,
      /parted/,
      /mount\s+-o\s+remount/,
      
      // Dangerous file operations
      /rm\s+-rf\s+\/($|\s)/,
      /rm\s+-rf\s+\/\*/,
      /find\s+\/\s+-delete/,
      /find\s+\/\s+-exec\s+rm/,
      
      // Network attacks (if network is disabled)
      /nc\s+-l/,
      /nmap/,
      
      // Privilege escalation attempts
      /sudo/,
      /su\s+-/,
      /chmod\s+[+\-]s/,
      /chown\s+root/,
      
      // Kernel/system manipulation
      /insmod/,
      /modprobe/,
      /sysctl/,
      
      // Process manipulation
      /kill\s+-9\s+-1/,
      /pkill\s+-9/,
      
      // Escape attempts
      /docker\s+run/,
      /chroot/,
    ];
  }

  isCommandSafe(command: string): boolean {
    // Check blocked commands
    for (const blockedCmd of this.securityConfig.blockedCommands) {
      if (command.includes(blockedCmd)) {
        return false;
      }
    }

    // Check dangerous patterns
    for (const pattern of this.dangerousPatterns) {
      if (pattern.test(command)) {
        return false;
      }
    }

    // Check for shell operators that could be dangerous
    const dangerousOperators = [
      "||", "&&", ";", "|", "`", "$(",
      ">>", ">", "<", "<<<", "<(", ">()"
    ];

    // Count occurrences of dangerous operators
    let operatorCount = 0;
    for (const op of dangerousOperators) {
      operatorCount += (command.match(new RegExp(op.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "g")) || []).length;
    }

    // Too many operators might indicate an attack
    if (operatorCount > 5) {
      return false;
    }

    // Check for attempts to access parent directories
    if (/\.\.\//.test(command)) {
      // Allow some legitimate uses but be cautious
      const parentDirCount = (command.match(/\.\.\//g) || []).length;
      if (parentDirCount > 2) {
        return false;
      }
    }

    // Check for environment variable manipulation that could be dangerous
    if (/export\s+(LD_PRELOAD|LD_LIBRARY_PATH|PATH)=/.test(command)) {
      return false;
    }

    // Check for attempts to download and execute scripts
    if (/(curl|wget)\s+.*\|\s*(bash|sh|python|perl|ruby|node)/.test(command)) {
      return false;
    }

    // Check for base64 decode attempts that might hide malicious commands
    if (/base64\s+-d.*\|\s*(bash|sh)/.test(command)) {
      return false;
    }

    return true;
  }

  sanitizeEnvironment(env: Record<string, string>): Record<string, string> {
    const sanitized = { ...env };
    
    // Remove dangerous environment variables
    const dangerousVars = [
      "LD_PRELOAD",
      "LD_LIBRARY_PATH",
      "BASH_ENV",
      "ENV",
      "CDPATH",
      "IFS"
    ];

    for (const varName of dangerousVars) {
      delete sanitized[varName];
    }

    return sanitized;
  }

  validatePath(path: string, allowedPaths: string[]): boolean {
    // Normalize the path
    const normalizedPath = path.replace(/\/+/g, "/").replace(/\/$/, "");

    // Check if path is within allowed paths
    for (const allowed of allowedPaths) {
      const normalizedAllowed = allowed.replace(/\/+/g, "/").replace(/\/$/, "");
      if (normalizedPath.startsWith(normalizedAllowed)) {
        return true;
      }
    }

    return false;
  }
}