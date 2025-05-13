# MMMM — Market Making Mega Machine

[![Python 3.8+](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![HyperLiquid](https://img.shields.io/badge/HyperLiquid-API-green.svg)](https://hyperliquid.xyz)
[![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)]()

```
███╗   ███╗███╗   ███╗███╗   ███╗███╗   ███╗
████╗ ████║████╗ ████║████╗ ████║████╗ ████║
██╔████╔██║██╔████╔██║██╔████╔██║██╔████╔██║
██║╚██╔╝██║██║╚██╔╝██║██║╚██╔╝██║██║╚██╔╝██║
██║ ╚═╝ ██║██║ ╚═╝ ██║██║ ╚═╝ ██║██║ ╚═╝ ██║
╚═╝     ╚═╝╚═╝     ╚═╝╚═╝     ╚═╝╚═╝     ╚═╝
═══════ Market Making Mega Machine ═══════
═══════════════════════════════════════════
```

A professional, streamlined trading platform for the HyperLiquid exchange, focusing on efficient market making with a clean interface.

## Core Features

- 🔄 Connect to HyperLiquid mainnet/testnet with ease
- 💰 View balances and positions with a single command
- 📊 Execute spot and perpetual market/limit orders 
- 📈 Specialized for market making with intelligent order placement

## Quick Setup

1. **Install:**
   ```bash
   git clone https://github.com/yourusername/mmmm-trading.git
   cd mmmm-trading
   pip install -r requirements.txt
   ```

2. **Configure:**
   Create `dontshareconfig.py` with your API credentials:
   ```python
   # Mainnet account credentials
   mainnet_wallet = ""  # Your mainnet wallet address
   mainnet_secret = ""  # Your mainnet private key
   # Testnet account credentials
   testnet_wallet = ""  # Your testnet wallet address
   testnet_secret = ""  # Your testnet private key
   ```

3. **Run:**
   ```bash
   python main.py
   ```

## Basic Command Reference

- `connect [mainnet|testnet]` - Connect to HyperLiquid
- `balance` - Show balances
- `positions` - Show open positions
- `orders [symbol]` - List open orders

### Spot Trading
```
buy <symbol> <quantity> [slippage]
sell <symbol> <quantity> [slippage]
limit_buy <symbol> <quantity> <price>
limit_sell <symbol> <quantity> <price>
```

### Perpetual Trading
```
perp_buy <symbol> <size> [leverage] [slippage]
perp_sell <symbol> <size> [leverage] [slippage]
perp_limit_buy <symbol> <size> <price> [leverage]
perp_limit_sell <symbol> <size> <price> [leverage]
close_position <symbol> [slippage]
set_leverage <symbol> <leverage>
```

## Market Making Guide

MMMM offers a powerful, focused market making strategy that places and manages orders around the current market price to capture the spread.

### Setting Up Market Making

1. **Connect to the exchange:**
   ```
   >>> connect mainnet  # or connect testnet
   Successfully connected to 0xb92e5A...
   ```

2. **Launch the market making strategy:**
   ```
   >>> select_strategy pure_mm
   ```

3. **Configure parameters:**

   | Parameter | Description | Default | Recommended Range |
   |-----------|-------------|---------|------------------|
   | symbol | Trading pair symbol | BTC | Any supported pair |
   | bid_spread | Percentage below mid price for buys | 0.0005 (0.05%) | 0.0005-0.005 |
   | ask_spread | Percentage above mid price for sells | 0.0005 (0.05%) | 0.0005-0.005 |
   | order_amount | Size of each order | 0.001 | Depends on asset |
   | refresh_time | Seconds between order refreshes | 30 | 10-60 |
   | is_perp | Trade perpetual contracts | False | True/False |
   | leverage | Leverage for perpetuals | 1 | 1-5 for beginners |

   Example configuration:
   ```
   symbol (Trading pair symbol) [BTC]: ETH
   bid_spread (Spread below mid price for buy orders (as a decimal)) [0.0005]: 0.001
   ask_spread (Spread above mid price for sell orders (as a decimal)) [0.0005]: 0.001
   order_amount (Size of each order) [0.001]: 0.01
   refresh_time (Time in seconds between order refresh) [30]: 20
   is_perp (Whether to trade perpetual contracts (True) or spot (False)) [False]: True
   leverage (Leverage to use for perpetual trading (if is_perp is True)) [1]: 2
   ```

4. **Monitor strategy performance:**
   ```
   >>> strategy_status
   === Active Strategy: Pure Market Making ===
   Module: pure_mm
   Status: Running
   Current state: Placed orders around mid price 3256.75
   Performance Metrics:
     symbol: ETH
     mid_price: 3256.75
     bid_price: 3253.49
     ask_price: 3260.01
     has_buy_order: True
     has_sell_order: True
     last_refresh: 2025-05-09 15:21:33
   ```

5. **Stop the strategy when desired:**
   ```
   >>> stop_strategy
   Stopping strategy: Pure Market Making
   Strategy stopped successfully.
   ```

### Market Making Tips

- **Appropriate Spreads**: Start with wider spreads (0.1-0.3%) and narrow them as you gain confidence
- **Order Size**: Keep orders small relative to your balance (1-5% of your portfolio per pair)
- **Asset Selection**: Choose assets with:
  - Higher volatility (for wider spreads)
  - Higher trading volume (for more fill opportunities)
  - Lower trading fees (to maximize profit margins)
- **Risk Management**:
  - Monitor your positions regularly
  - Use `stop_strategy` during high market volatility
  - Set reasonable leverage (1-3x) when using perpetuals
- **Performance Tracking**: Use `strategy_status` regularly to monitor performance

## Strategy Trading Commands

```
select_strategy [strategy_name]  - Select and configure a trading strategy
strategy_status                  - Check the status of the current strategy
stop_strategy                    - Stop the currently running strategy
strategy_params [strategy_name]  - View parameters of a strategy
help_strategies                  - Show help for trading strategies
```

### Order Management
```
cancel <symbol> <order_id>
cancel_all [symbol]
```

## Help Commands
- `help` - Display available commands
- `help_strategies` - Trading strategy help
- `clear` - Clear screen
- `exit` - Exit application

## Interface Changes in v2.0.0

- 🎨 Redesigned interface with a cleaner, more focused experience
- 🚀 Renamed to "MMMM — Market Making Mega Machine" to reflect the specialized focus
- 🔄 Streamlined command set focusing on essential trading and market making functionality
- 📈 Optimized for professional market makers with direct access to key commands

---

<p align="center">
  <sub>Built by a Vibe Coder,lol</sub>
</p>
