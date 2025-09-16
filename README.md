# MMMM — Market Making Mega Machine

[![Python 3.8+](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
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
- 🚨 Emergency order cancellation and auto-cancellation features
- 📊 Comprehensive monitoring and alerting system

## Quick Setup

1. **Install:**
   ```bash
   git clone https://github.com/AlwaysUbaid/MarketMakingMegaMachine.git
   cd MarketMakingMegaMachine
   chmod +x install.sh
   sudo ./install.sh
   ```

2. **Configure:**
   Create `.env` with your API credentials:
   ```python
   # Mainnet account credentials
   WALLET_ADDRESS = ""  # Your mainnet wallet address
   WALLET_SECRET = ""  # Your mainnet wallet secret
   ```

3. **Run:**
   ```bash
   # Start the main service
   sudo systemctl start mmmm
   
   # Start the monitoring service
   sudo systemctl start mmmm-monitor
   ```

## Development Setup

1. **Create and activate virtual environment:**
   ```bash
   # Create virtual environment
   python3 -m venv venv
   
   # Activate virtual environment
   # On macOS/Linux:
   source venv/bin/activate
   # On Windows:
   .\venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables:**
   ```bash
   # Copy example environment file
   cp example.env .env
   
   # Edit .env with your credentials
   nano .env  # or use your preferred editor
   ```

4. **Verify installation:**
   ```bash
   # Run with verbose logging
   python main.py -v
   
   # Test emergency cancel-all
   python main.py -ca
   ```

## Command-Line Usage

You can run strategies directly from the command line:

```bash
# Basic usage
python main.py -s ubtc_mm

# With testnet
python main.py -s ueth_mm -t

# With custom parameters
python main.py -s pure_mm --strategy-params '{"bid_spread": 0.001, "ask_spread": 0.001, "order_amount": 0.1}'

# With verbose logging
python main.py -s buddy_mm -v

# Emergency cancel all orders
python main.py -ca
```

Available strategies:
- `ubtc_mm`: UBTC market making
- `ueth_mm`: UETH market making
- `pure_mm`: Pure market making
- `buddy_mm`: Buddy market making
- `usol_mm`: USOL market making
- `ufart_mm`: UFART market making

## Emergency Features

### Auto-Cancellation

The platform includes automatic order cancellation in response to:
- Insufficient balance errors
- System errors
- Network issues

Auto-cancellation is implemented across all strategy files:
- `ubtc_mm.py`
- `ueth_mm.py`
- `usol_mm.py`
- `ufart_mm.py`
- `pure_mm.py`
- `buddy_mm.py`

### Emergency Commands

1. **Cancel All Orders:**
   ```bash
   # Basic usage
   mmmm-cancel-all
   
   # With verbose logging
   mmmm-cancel-all -v
   
   # On testnet
   mmmm-cancel-all -t
   ```

2. **Check Status:**
   ```bash
   # View service status
   sudo systemctl status mmmm
   
   # View monitoring status
   sudo systemctl status mmmm-monitor
   ```

3. **View Logs:**
   ```bash
   # Main service logs
   tail -f /var/log/mmmm/mmmm.log
   
   # Monitoring logs
   tail -f /var/log/mmmm/mmmm-monitor.log
   ```

## Monitoring and Alerts

The platform includes a comprehensive monitoring system that:
- Tracks auto-cancellation events
- Monitors error patterns
- Sends email alerts for critical events
- Maintains detailed logs

Configure alerts in `/usr/local/bin/mmmm-monitor`:
```bash
# Edit the ALERT_EMAIL variable
ALERT_EMAIL="your-email@example.com"
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
- 🚨 Added emergency features and auto-cancellation
- 📊 Enhanced monitoring and alerting system

---

<p align="center">
  <sub>Built by a Vibe Coder,lol</sub>
</p>
