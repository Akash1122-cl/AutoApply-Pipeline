#!/usr/bin/env bash

# Exit immediately if any command fails
set -o errexit

echo "🚀 Starting AutoApply Pipeline Production Services..."

# 1. Start the Orchestrator Daemon in the background
echo "⏰ Launching Orchestrator Daemon (running on 9:00 AM IST daily trigger)..."
python -m src.orchestrator.main --daemon &
DAEMON_PID=$!

# 2. Start the FastAPI Dashboard Web App in the foreground
echo "📊 Launching FastAPI Dashboard Observability UI..."
uvicorn src.web.app:app --host 0.0.0.0 --port ${PORT:-8000} &
DASHBOARD_PID=$!

# Handle shutdown signals gracefully
cleanup() {
    echo "👋 Shutting down services..."
    kill $DAEMON_PID 2>/dev/null || true
    kill $DASHBOARD_PID 2>/dev/null || true
    exit 0
}
trap cleanup SIGINT SIGTERM

# Wait for either background process to exit
wait -n

# If we get here, one of the processes has exited. Shutdown the other and exit with error.
echo "⚠️ One of the services stopped unexpectedly. Initiating teardown..."
cleanup
