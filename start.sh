#!/bin/bash
# Job Radar — start script
set -e

cd /workspace/job-radar

# Install Playwright browsers if not present
python3 -m playwright install chromium --with-deps 2>/dev/null || true

echo "Starting Job Radar scheduler..."
exec python3 src/scheduler.py
