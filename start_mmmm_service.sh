#!/bin/bash

# MMMM Trading Bot Service Starter
# This script starts the MMMM trading bot as a background service
# Usage: ./start_mmmm_service.sh <strategy_name> [--testnet]

# Check for required arguments
if [ $# -lt 1 ]; then
    echo "Usage: $0 <strategy_name> [--testnet]"
    exit 1
fi

STRATEGY=$1
TESTNET_FLAG=""

# Check if testnet flag is provided
if [[ "$2" == "--testnet" ]]; then
    TESTNET_FLAG="-t"
    echo "Running on testnet..."
else
    echo "Running on mainnet..."
fi

# Create logs directory if it doesn't exist
mkdir -p logs

# Generate log filename with timestamp
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="logs/${STRATEGY}_${TIMESTAMP}.log"

echo "Starting MMMM bot with strategy: $STRATEGY"
echo "Logs will be saved to: $LOG_FILE"

# Start the bot as a background process with nohup
nohup python main.py $TESTNET_FLAG -s $STRATEGY -v --log-file $LOG_FILE > /dev/null 2>&1 &

# Save the process ID
PID=$!
echo $PID > "${STRATEGY}.pid"
echo "Bot started with PID: $PID"
echo "To stop the bot, run: kill $PID"