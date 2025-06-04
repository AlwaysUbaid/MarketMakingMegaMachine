#!/bin/bash

# Emergency cancel-all script for MMMM Trading Platform
# This script will connect to the exchange and cancel all open orders

# Set up logging
LOG_DIR="logs"
mkdir -p $LOG_DIR
LOG_FILE="$LOG_DIR/emergency_cancel_$(date +%Y%m%d_%H%M%S).log"

# Function to log messages
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Function to handle errors
handle_error() {
    log "ERROR: $1"
    exit 1
}

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    handle_error "Python 3 is not installed"
fi

# Check if we're in the correct directory
if [ ! -f "main.py" ]; then
    handle_error "Please run this script from the MMMM root directory"
fi

# Parse command line arguments
VERBOSE=""
TESTNET=""
while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--verbose)
            VERBOSE="-v"
            shift
            ;;
        -t|--testnet)
            TESTNET="-t"
            shift
            ;;
        *)
            log "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Log start of emergency cancellation
log "Starting emergency order cancellation"
log "Verbose mode: ${VERBOSE:+enabled}"
log "Testnet mode: ${TESTNET:+enabled}"

# Run the cancel-all command
log "Executing cancel-all command..."
if ! python3 main.py -ca $VERBOSE $TESTNET; then
    handle_error "Failed to execute cancel-all command"
fi

# Verify cancellation
log "Verifying order cancellation..."
if ! python3 main.py -o; then
    log "WARNING: Failed to verify order cancellation"
else
    log "Order verification complete"
fi

log "Emergency cancellation completed successfully"
exit 0 