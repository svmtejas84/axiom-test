#!/bin/bash

# Axiom Clean Execution Wrapper
# Starts the backend, waits for health check, and launches the interactive orchestrator.

PORT=8000
API_URL="http://127.0.0.1:$PORT/health"

# 1. Check if port is already in use
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null ; then
    echo "[!] Port $PORT is already in use. Assuming server is already running."
    ALREADY_RUNNING=true
else
    echo "[+] Starting Axiom API server in background..."
    # Start uvicorn and redirect output to a log file
    uvicorn api.main:app --host 0.0.0.0 --port $PORT > .api_server.log 2>&1 &
    SERVER_PID=$!
    ALREADY_RUNNING=false
    
    # Cleanup function
    cleanup() {
        if [ "$ALREADY_RUNNING" = false ]; then
            echo -e "\n[+] Shutting down background API server (PID: $SERVER_PID)..."
            kill $SERVER_PID
        fi
    }
    trap cleanup EXIT
fi

# 2. Wait for Health Check
echo -n "[+] Waiting for API to be healthy..."
MAX_RETRIES=30
COUNT=0
while ! curl -s "$API_URL" | grep -q '"status":"healthy"'; do
    echo -n "."
    sleep 1
    COUNT=$((COUNT+1))
    if [ $COUNT -ge $MAX_RETRIES ]; then
        echo -e "\n[!] Timeout waiting for API to start. Check .api_server.log for errors."
        exit 1
    fi
done
echo " [OK]"

# 3. Execute Main Orchestrator
python main_execution.py

# Cleanup will happen automatically via trap if we started the server
