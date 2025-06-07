# Market Making Mega Machine (MMMM) - Deployment Guide

## Table of Contents
1. [Overview](#overview)
2. [System Requirements](#system-requirements)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [Available Strategies](#available-strategies)
6. [Usage Guide](#usage-guide)
7. [Emergency Procedures](#emergency-procedures)
8. [Monitoring and Maintenance](#monitoring-and-maintenance)
9. [Troubleshooting](#troubleshooting)
10. [Security Considerations](#security-considerations)
11. [Performance Optimization](#performance-optimization)
12. [Limitations and Known Issues](#limitations-and-known-issues)

## Overview

MMMM is a professional-grade market making platform designed specifically for the HyperLiquid exchange. It provides automated market making capabilities with a focus on safety, reliability, and performance.

### Key Features
- 🔄 Automated market making for multiple assets
- 💰 Real-time balance and position tracking
- 📊 Advanced order management
- 🚨 Emergency order cancellation
- 📈 Performance monitoring
- 🔒 Secure API key management

### Pros
- Professional-grade market making capabilities
- Multiple strategy support
- Robust error handling
- Emergency procedures built-in
- Comprehensive monitoring
- Easy to use CLI interface

### Cons
- Requires technical knowledge to deploy
- Needs constant monitoring
- Requires significant capital for effective market making
- Limited to HyperLiquid exchange
- No GUI interface (CLI only)

## System Requirements

### Hardware Requirements
- CPU: 2+ cores
- RAM: 4GB minimum
- Storage: 10GB free space
- Network: Stable internet connection

### Software Requirements
- Operating System: Linux (recommended), macOS, or Windows
- Python 3.8 or higher
- pip (Python package manager)
- Git

## Installation

### 1. Clone the Repository
```bash
git clone https://github.com/AlwaysUbaid/MarketMakingMegaMachine.git
cd MarketMakingMegaMachine
```

### 2. Install Dependencies
```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate

# Install required packages
pip install -r requirements.txt
```

### 3. System Installation (Linux)
```bash
# Make install script executable
chmod +x install.sh

# Run installation script (requires sudo)
sudo ./install.sh
```

## Configuration

### 1. Environment Setup
Create a `.env` file in the project root:
```bash
# Copy example environment file
cp example.env .env

# Edit .env with your credentials
nano .env
```

Required environment variables:
```
WALLET_ADDRESS = "your_wallet_address"
WALLET_SECRET = "your_wallet_secret"
```

### 2. Strategy Configuration
Each strategy can be configured with custom parameters. Available strategies:

1. **UBTC Market Making**
   - Symbol: UBTC-PERP
   - Default spread: 0.05%
   - Minimum order size: 0.001 BTC

2. **UETH Market Making**
   - Symbol: UETH-PERP
   - Default spread: 0.05%
   - Minimum order size: 0.01 ETH

3. **Pure Market Making**
   - Customizable for any asset
   - Flexible spread settings
   - Advanced order distribution

4. **Buddy Market Making**
   - Pairs trading strategy
   - Correlation-based order placement
   - Risk management features

5. **USOL Market Making**
   - Symbol: USOL-PERP
   - Default spread: 0.05%
   - Minimum order size: 1 USOL

6. **UFART Market Making**
   - Symbol: UFART-PERP
   - Default spread: 0.05%
   - Minimum order size: 100 UFART

## Usage Guide

### 1. Starting the Platform
```bash
# Start with verbose logging
python main.py -v

# Start with specific strategy
python main.py -s ubtc_mm

# Start with testnet
python main.py -s ueth_mm -t
```

### 2. Basic Commands
```
connect [mainnet|testnet]  - Connect to HyperLiquid
balance                    - Show balances
positions                 - Show open positions
orders [symbol]           - List open orders
```

### 3. Trading Commands
```
# Spot Trading
buy <symbol> <quantity> [slippage]
sell <symbol> <quantity> [slippage]
limit_buy <symbol> <quantity> <price>
limit_sell <symbol> <quantity> <price>

# Perpetual Trading
perp_buy <symbol> <size> [leverage] [slippage]
perp_sell <symbol> <size> [leverage] [slippage]
perp_limit_buy <symbol> <size> <price> [leverage]
perp_limit_sell <symbol> <size> <price> [leverage]
```

### 4. Strategy Management
```
select_strategy [strategy_name]  - Select and configure a strategy
strategy_status                  - Check strategy status
stop_strategy                    - Stop current strategy
strategy_params [strategy_name]  - View strategy parameters
```

## Emergency Procedures

### 1. Emergency Cancel All Orders
```bash
# Using CLI
mmmm-cancel-all

# With verbose logging
mmmm-cancel-all -v

# On testnet
mmmm-cancel-all -t
```

### 2. Service Management
```bash
# Check service status
sudo systemctl status mmmm

# Stop service
sudo systemctl stop mmmm

# View logs
tail -f /var/log/mmmm/mmmm.log
```

## Monitoring and Maintenance

### 1. Log Monitoring
```bash
# Main service logs
tail -f /var/log/mmmm/mmmm.log

# Monitoring logs
tail -f /var/log/mmmm/mmmm-monitor.log
```

### 2. Performance Monitoring
- Monitor auto-cancellation events
- Track error patterns
- Review strategy performance metrics
- Check system resource usage

### 3. Regular Maintenance
- Update dependencies regularly
- Monitor disk space
- Check log rotation
- Verify API key validity

## Troubleshooting

### Common Issues

1. **Connection Issues**
   - Verify internet connection
   - Check API credentials
   - Ensure correct network (mainnet/testnet)

2. **Order Issues**
   - Verify sufficient balance
   - Check order size limits
   - Review spread settings

3. **Strategy Issues**
   - Check strategy parameters
   - Verify market data availability
   - Review error logs

### Debug Mode
```bash
# Enable debug logging
python main.py -v --log-file debug.log
```

## Security Considerations

### 1. API Key Security
- Never share API keys
- Use environment variables
- Regular key rotation
- Limited permissions

### 2. System Security
- Regular updates
- Firewall configuration
- Access control
- Secure storage

### 3. Best Practices
- Use testnet for testing
- Start with small amounts
- Regular security audits
- Backup configuration

## Performance Optimization

### 1. System Optimization
- Use SSD storage
- Optimize network settings
- Regular system maintenance
- Monitor resource usage

### 2. Strategy Optimization
- Adjust refresh rates
- Optimize order sizes
- Fine-tune spreads
- Monitor slippage

### 3. Network Optimization
- Use stable connection
- Consider dedicated line
- Monitor latency
- Regular speed tests

## Limitations and Known Issues

### 1. Platform Limitations
- CLI-only interface
- Single exchange support
- No mobile access
- Limited strategy customization

### 2. Known Issues
- Network latency impact
- Order book depth limitations
- Market volatility effects
- System resource constraints

### 3. Risk Factors
- Market volatility
- Technical issues
- Network problems
- Exchange limitations

## Support and Resources

### 1. Documentation
- README.md
- Strategy guides
- API documentation
- Configuration guide

### 2. Community
- GitHub issues
- Discord community
- Telegram group
- Stack Overflow

### 3. Updates
- Regular releases
- Security patches
- Feature updates
- Bug fixes

---