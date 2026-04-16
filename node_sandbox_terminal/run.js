#!/usr/bin/env node

// This wrapper ensures the server runs correctly when executed via npx
import { spawn } from 'child_process';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const child = spawn('node', [join(__dirname, 'dist', 'index.js')], {
  stdio: 'inherit',
  env: process.env
});

child.on('exit', (code) => {
  process.exit(code || 0);
});