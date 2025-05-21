#!/bin/bash

# MMMM Trading Bot Service Stopper
# This script stops the MMMM trading bot process
# Usage: ./stop_mmmm_service.sh <strategy_name>

# Check for required arguments
if [ $# -lt 1 ]; then
    echo "Usage: $0 <strategy_name>"
    exit 1
fi

STRATEGY=$1
PID_FILE="${STRATEGY}.pid"

# Check if PID file exists
if [ ! -f "$PID_FILE" ]; then
    echo "PID file not found. Is the bot running?"
    exit 1
fi

# Read PID from file
PID=$(cat $PID_FILE)

# Check if process exists
if ! ps -p $PID > /dev/null; then
    echo "Process with PID $PID not found. Bot might have crashed."
    rm $PID_FILE
    exit 1
fi

# Send graceful termination signal
echo "Stopping MMMM bot with strategy: $STRATEGY (PID: $PID)"
kill $PID

# Wait for process to terminate
for i in {1..30}; do
    if ! ps -p $PID > /dev/null; then
        echo "Bot stopped successfully"
        rm $PID_FILE
        exit 0
    fi
    echo "Waiting for bot to stop... ($i/30)"
    sleep 1
done

# Force kill if still running
echo "Bot did not stop gracefully. Force stopping..."
kill -9 $PID
if ! ps -p $PID > /dev/null; then
    echo "Bot force stopped successfully"
else
    echo "Failed to stop bot. Please check manually."
fi

# Clean up PID file
rm $PID_FILE