#!/usr/bin/env bash
# Exit on error
set -o errexit

# 1. Build the React frontend
echo "=== Building React Frontend ==="
cd sentinel-frontend
npm install
npm run build
cd ..

# 2. Install backend Python requirements
echo "=== Installing Python Dependencies ==="
pip install --upgrade pip
pip install -r requirements.txt

echo "=== Build Completed Successfully ==="
