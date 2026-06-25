#!/bin/bash
# Job Radar — start script for Render
set -e

cd "${RENDER_PROJECT_DIR:-$(pwd)}"

echo "Working dir: $(pwd)"
ls -la
echo "---"
echo "Python: $(python3 --version)"
echo "Starting Job Radar scheduler..."
exec python3 src/scheduler.py