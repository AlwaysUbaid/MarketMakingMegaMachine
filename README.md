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
- 🚀 Deployment-ready with command-line configuration
- 🔧 Multiple market making strategies available

## Quick Setup

1. **Install:**
   ```bash
   git clone https://github.com/AlwaysUbaid/MarketMakingMegaMachine.git
   cd MarketMakingMegaMachine
   pip install -r requirements.txt
   ```

2. **Configure:**
   Create `.env` file with your API credentials:
   ```
   WALLET_ADDRESS=your_wallet_address
   WALLET_SECRET=your_wallet_secret
   ```

3. **Run:**
   ```bash
   python main.py -s <strategy_name>
   ```

## Available Strategies

- `ubtc_mm`: UBTC Market Making
- `ueth_mm`: UETH Market Making
- `usol_mm`: USOL Market Making
- `ufart_mm`: UFART Market Making
- `pure_mm`: Pure Market Making
- `buddy_mm`: Buddy Market Making

## Deployment-Ready Commands

### Basic Strategy Execution
```bash
# Run UBTC market making strategy
python main.py -s ubtc_mm

# Run with testnet
python main.py -s ubtc_mm -t

# Run with verbose logging
python main.py -s ubtc_mm -v

# Run with log file
python main.py -s ubtc_mm --log-file strategy.log
```

### Custom Parameters
```bash
# Custom trading pair and spreads
python main.py -s ubtc_mm --symbol UBTC/USDC --bid-spread 0.0001 --ask-spread 0.0002

# Custom order size and refresh time
python main.py -s ubtc_mm --order-amount 0.001 --refresh-time 30

# Perpetual trading with leverage
python main.py -s ubtc_mm --is-perp --leverage 2

# Enable dynamic spreads
python main.py -s ubtc_mm --use-dynamic-spreads
```

### Advanced Configuration
```bash
# Using JSON parameters for complex configurations
python main.py -s ubtc_mm -p '{
    "symbol": {"value": "UBTC/USDC"},
    "bid_spread": {"value": 0.0001},
    "ask_spread": {"value": 0.0002},
    "order_amount": {"value": 0.001},
    "refresh_time": {"value": 30},
    "is_perp": {"value": true},
    "leverage": {"value": 2},
    "use_dynamic_spreads": {"value": true}
}'

# Load parameters from file
python main.py -s ubtc_mm -p @config.json
```

### Production Deployment
```bash
# Run in background with logging
nohup python main.py -s ubtc_mm -v --log-file /var/log/mmmm/ubtc_mm.log &

# Run with systemd service
sudo systemctl start mmmm-ubtc.service
```

## Strategy Parameters

| Parameter | Description | Default | Recommended Range |
|-----------|-------------|---------|------------------|
| symbol | Trading pair symbol | UBTC/USDC | Any supported pair |
| bid_spread | Percentage below mid price for buys | 0.0001 (0.01%) | 0.0001-0.001 |
| ask_spread | Percentage above mid price for sells | 0.0002 (0.02%) | 0.0001-0.001 |
| order_amount | Size of each order | 0.001 | Depends on asset |
| refresh_time | Seconds between order refreshes | 30 | 10-60 |
| is_perp | Trade perpetual contracts | False | True/False |
| leverage | Leverage for perpetuals | 1 | 1-5 for beginners |
| use_dynamic_spreads | Dynamic spread adjustment | False | True/False |

## Market Making Tips

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

## Production Deployment Guide

1. **System Requirements:**
   - Python 3.8 or higher
   - 2GB RAM minimum
   - Stable internet connection
   - 24/7 uptime recommended

2. **Security Setup:**
   ```bash
   # Set proper permissions
   chmod 600 .env
   chmod 600 *.json
   
   # Create dedicated user
   sudo useradd -m -s /bin/bash mmmm
   sudo usermod -aG sudo mmmm
   ```

3. **Service Installation:**
   ```bash
   # Copy service file
   sudo cp mmmm-ubtc.service /etc/systemd/system/
   
   # Enable and start service
   sudo systemctl daemon-reload
   sudo systemctl enable mmmm-ubtc.service
   sudo systemctl start mmmm-ubtc.service
   ```

4. **Monitoring:**
   ```bash
   # Check service status
   sudo systemctl status mmmm-ubtc.service
   
   # View logs
   tail -f /var/log/mmmm/ubtc_mm.log
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
- 🔧 Added deployment-ready command-line interface
- 📝 Enhanced documentation and examples

---

<p align="center">
  <sub>Built by a Vibe Coder,lol</sub>
</p>
