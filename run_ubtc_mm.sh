#!/bin/bash

# Run UBTC market making strategy
# Usage: ./run_ubtc_mm.sh [--testnet]

# Check if testnet flag is provided
if [[ "$1" == "--testnet" ]]; then
    TESTNET_FLAG="-t"
    echo "Running on testnet..."
else
    TESTNET_FLAG=""
    echo "Running on mainnet..."
fi

# Default parameters for UBTC market making
PARAMS='{
    "symbol": {"value": "UBTC/USDC"},
    "bid_spread": {"value": 0.00011},
    "ask_spread": {"value": 0.00012},
    "order_amount": {"value": 0.00013},
    "refresh_time": {"value": 10},
    "is_perp": {"value": false}
}'

# Run the strategy
python main.py $TESTNET_FLAG -s ubtc_mm -p "$PARAMS" -v --log-file ubtc_mm.log