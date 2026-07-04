#!/bin/bash
# start.sh — Start all project services
# Run this after every reboot:  bash start.sh

set -e

echo "=== Starting Ollama ==="
if brew services list 2>/dev/null | grep -q "^ollama.*started"; then
    echo "Ollama already running"
else
    brew services start ollama
    echo "Waiting for Ollama..."
    sleep 3
fi

echo "=== Verifying Ollama ==="
if curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "Ollama OK — models available"
    curl -s http://localhost:11434/api/tags | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'  {len(d.get(\"models\",[]))} models loaded')" 2>/dev/null || true
else
    echo "WARNING: Ollama not responding. Check: ollama serve"
fi

echo ""
echo "=== Ready ==="
echo "Run pipeline:"
echo "  cd agents && FORMAT=short CATEGORY=\"AI Explained\" TOPIC=\"<topic>\" python3 run_pipeline.py"
echo "  cd agents && FORMAT=long  CATEGORY=\"AI Explained\" TOPIC=\"<topic>\" python3 run_pipeline.py"
echo "Dashboard:"
echo "  cd dashboard && npm run dev"
