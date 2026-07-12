#!/bin/bash
# MindMesh - Start All Services (for Git Bash / WSL / Linux / macOS)
cd "$(dirname "$0")" || exit 1

echo "============================================"
echo "   MindMesh - Starting All Services"
echo "============================================"
echo ""

# --- Ensure web/.env.local exists ---
if [ ! -f web/.env.local ]; then
  echo "[setup] Creating web/.env.local with API URL..."
  echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > web/.env.local
else
  echo "[setup] web/.env.local found"
fi

echo ""

cleanup() {
  echo ""
  echo "Shutting down MindMesh..."
  kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
  wait $BACKEND_PID $FRONTEND_PID 2>/dev/null
  echo "All services stopped."
  exit 0
}
trap cleanup SIGINT SIGTERM

# Start Python backend
echo "[1/2] Starting Python FastAPI backend (port 8000)..."
python -m uvicorn server.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

sleep 2

# Start Next.js frontend
echo "[2/2] Starting Next.js frontend (port 3000)..."
cd web && npm run dev &
FRONTEND_PID=$!

echo ""
echo "============================================"
echo "  Both servers are starting up!"
echo "  Frontend: http://localhost:3000"
echo "  Backend:  http://localhost:8000"
echo "============================================"
echo "  Press Ctrl+C to stop all services."
echo ""

wait
