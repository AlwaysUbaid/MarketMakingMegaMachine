# Cross-Exchange Arbitrage System Integration

This document provides an overview of the cross-exchange arbitrage functionality added to the existing market making bot.

## Overview

The cross-exchange arbitrage system enables trading across Hyperliquid and Bybit exchanges, identifying price differences and executing trades to capture profits from these inefficiencies.

## Components

1. **Exchange Connectors**: Connect to both Hyperliquid and Bybit
2. **Market Data Normalizers**: Standardize market data from different exchanges
3. **Delta Engine**: Analyze price differentials to identify opportunities
4. **Inventory Tracker**: Monitor balances across exchanges
5. **Arbitrage Strategy**: Execute trades based on opportunities

## Terminal Commands

The system adds the following commands to the terminal UI:

- `connect_bybit [testnet]`: Connect to Bybit exchange
- `bybit_balance`: Show current balances on Bybit
- `bybit_market <symbol>`: Get market data from Bybit
- `cross_market <hl_symbol> <bybit_symbol>`: Compare markets across exchanges
- `start_arbitrage <symbol> [mode]`: Start the arbitrage strategy
- `stop_arbitrage`: Stop the arbitrage strategy
- `arb_status`: Check arbitrage strategy status

## Configuration

The system uses `exchange_config.json` to store configuration:

```json
{
  "symbol_mapping": {
    "UBTC/USDC": {
      "hyperliquid": "UBTC/USDC",
      "bybit": "BTCUSDT"
    },
    "UETH/USDC": {
      "hyperliquid": "UETH/USDC",
      "bybit": "ETHUSDT"
    }
  },
  "arbitrage_config": {
    "UBTC/USDC": {
      "enabled": true,
      "min_delta_percentage": 0.1,
      "max_order_size": 0.01,
      "max_inventory_imbalance": 0.03
    }
  }
}