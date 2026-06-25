#!/bin/bash
# Job Radar — start script for Render
set -e

# On Render the code lives in /opt/render/project/src
# Locally it lives wherever the user cloned the repo
if [ -d "/opt/render/project/src" ]; then
    cd /opt/render/project/src
elif [ -n "$RENDER_PROJECT_DIR" ]; then
    cd "$RENDER_PROJECT_DIR"
else
    # fallback: stay in current dir
    echo "Using current dir: $(pwd)"
fi

echo "Working dir: $(pwd)"
ls -la
echo "---"
echo "Python: $(python3 --version)"
echo "Starting Job Radar scheduler..."
exec python3 src/scheduler.py