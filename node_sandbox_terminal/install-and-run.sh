#!/bin/bash
# Quick install and run script

TEMP_DIR=$(mktemp -d)
cd $TEMP_DIR

# Clone the repo (you'll need to configure git credentials)
git clone https://github.com/yourusername/node-sandbox-terminal.git
cd node-sandbox-terminal

# Install and run
npm install
npm run build
node dist/index.js

# Cleanup on exit
trap "rm -rf $TEMP_DIR" EXIT