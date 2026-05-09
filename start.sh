#!/usr/bin/env bash
# start.sh — launch backend then frontend
# Usage: ./start.sh

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Starting OpenClaw backend ==="
cd "$PROJECT_DIR"
source backend/.venv/bin/activate
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"

# Wait a moment for the backend to initialise before starting the frontend
sleep 2

echo "=== Starting OpenClaw frontend ==="
cd "$PROJECT_DIR/frontend"
npm run dev &
FRONTEND_PID=$!
echo "Frontend PID: $FRONTEND_PID"

echo ""
echo "Backend  → http://localhost:8000"
echo "Frontend → http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop both."

# Trap Ctrl+C and kill both processes
trap "echo 'Stopping...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM

# Wait for both
wait $BACKEND_PID $FRONTEND_PID
