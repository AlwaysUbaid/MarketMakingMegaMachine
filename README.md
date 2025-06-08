# MMMM — Market Making Mega Machine API

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

A professional, cloud-ready API for algorithmic trading and market making on HyperLiquid.

---

## Table of Contents

- [Features](#features)
- [Quick Start](#quick-start)
- [API Overview](#api-overview)
- [Authentication](#authentication)
- [Endpoints](#endpoints)
  - [Account](#account)
  - [Order](#order)
  - [Strategy](#strategy)
- [Example Usage](#example-usage)
- [Deployment](#deployment)
- [Contributing](#contributing)
- [License](#license)

---

## Features

- 🔄 Connect to HyperLiquid mainnet/testnet via API
- 💰 Query balances, positions, and open orders
- 🛒 Place/cancel spot and perpetual orders
- 🤖 Start/stop/manage market making strategies
- 🚨 Emergency cancel-all and auto-cancellation
- 📊 Designed for integration with web frontends and SaaS platforms

---

## Quick Start

1. **Clone and install dependencies:**
   ```bash
   git clone https://github.com/AlwaysUbaid/MarketMakingMegaMachine.git
   cd MarketMakingMegaMachine
   pip install -r requirements.txt
   ```

2. **Run the API server:**
   ```bash
   python api.py
   ```
   The API will be available at `http://localhost:8000`.

3. **Interactive docs:**  
   Visit [http://localhost:8000/docs](http://localhost:8000/docs) for Swagger UI.

---

## API Overview

All endpoints are grouped and RESTful.  
**Base URL:** `http://localhost:8000`

### Authentication

- **Connect to the exchange** (required before other actions):

  **POST** `/connect`
  ```json
  {
    "wallet_address": "0x...",
    "wallet_secret": "your_private_key",
    "use_testnet": false
  }
  ```
  **Response:**
  ```json
  { "status": "success", "message": "Connected to exchange" }
  ```

---

## Endpoints

### Account

- **GET `/balances`**  
  Get all balances (spot and perp).
  ```json
  {
    "status": "success",
    "data": {
      "spot": [
        { "asset": "UBTC", "available": 0.1, "total": 0.1, "in_orders": 0.0 }
      ],
      "perp": {
        "account_value": 1000.0,
        "margin_used": 100.0,
        "position_value": 0.0
      }
    }
  }
  ```

- **GET `/positions`**  
  Get all open positions.
  ```json
  {
    "status": "success",
    "data": [
      {
        "symbol": "UBTC",
        "size": 0.01,
        "entry_price": 30000.0,
        "mark_price": 30100.0,
        "liquidation_price": 25000.0,
        "unrealized_pnl": 10.0,
        "margin_used": 50.0
      }
    ]
  }
  ```

---

### Order

- **GET `/orders?symbol=UBTC`**  
  List open orders (optionally filter by symbol).

- **POST `/orders/market`**  
  Place a market order.
  ```json
  {
    "symbol": "UBTC",
    "size": 0.01,
    "order_type": "buy",  // or "sell"
    "slippage": 0.05
  }
  ```
  **Response:**  
  Returns order execution result from the exchange.

- **POST `/orders/limit`**  
  Place a limit order.
  ```json
  {
    "symbol": "UBTC",
    "size": 0.01,
    "price": 30000,
    "order_type": "buy"  // or "sell"
  }
  ```

- **DELETE `/orders/{symbol}/{order_id}`**  
  Cancel a specific order.

- **DELETE `/orders?symbol=UBTC`**  
  Cancel all orders (optionally filter by symbol).

---

### Strategy

- **GET `/strategies`**  
  List available strategies.
  ```json
  {
    "status": "success",
    "data": [
      { "module": "pure_mm", "name": "Pure Market Making", "description": "..." }
    ]
  }
  ```

- **GET `/strategies/{strategy_name}/params`**  
  Get parameters for a strategy.

- **POST `/strategies/{strategy_name}/start`**  
  Start a strategy.
  ```json
  {
    "params": {
      "symbol": "UBTC/USDC",
      "bid_spread": 0.001,
      "ask_spread": 0.001,
      "order_amount": 0.01,
      "refresh_time": 10,
      "is_perp": false,
      "leverage": 1
    }
  }
  ```
  **Response:**
  ```json
  { "status": "success", "message": "Started strategy: pure_mm" }
  ```

- **POST `/strategies/stop`**  
  Stop the currently running strategy.
  
  **Request:**
  ```json
  {}
  ```
  **Response:**
  ```json
  { "status": "success", "message": "Strategy stopped" }
  ```

- **GET `/strategies/status`**  
  Get the status of the currently running strategy.
  
  **Response:**
  ```json
  {
    "status": "success",
    "data": {
      "module": "pip_mm",
      "name": "PIP Market Making",
      "running": true,
      "params": {
        "symbol": "PIP/USDC",
        "bid_spread": 0.00011,
        "ask_spread": 0.00012,
        "order_amount": 0.55,
        "refresh_time": 10,
        "order_max_age": 30,
        "is_perp": false,
        "leverage": 1
      }
    }
  }
  ```

---

## Example Usage

**Connect and start a strategy (Python):**
```python
import requests

# Connect
r = requests.post("http://localhost:8000/connect", json={
    "wallet_address": "...",
    "wallet_secret": "...",
    "use_testnet": False
})
print(r.json())

# Start a strategy
r = requests.post("http://localhost:8000/strategies/pure_mm/start", json={
    "params": {
        "symbol": "UBTC/USDC",
        "bid_spread": 0.001,
        "ask_spread": 0.001,
        "order_amount": 0.01,
        "refresh_time": 10,
        "is_perp": False,
        "leverage": 1
    }
})
print(r.json())
```

---

## Deployment

- **Production:** Use a process manager (e.g., systemd, pm2) and a reverse proxy (e.g., Nginx).
- **Cloud:** Deploy on any cloud VM or container platform. Expose port 8000 or use a custom domain.
- **Security:** Protect `/connect` and trading endpoints with authentication in production.

---

## Contributing

Pull requests and issues are welcome!  
Please open an issue to discuss your feature or bugfix idea.

---

## License

MIT License

---

<p align="center">
  <sub>Built by a Vibe Coder, lol</sub>
</p>

---

**For full API details, see the [Swagger UI](http://localhost:8000/docs) after running the server.**

---
