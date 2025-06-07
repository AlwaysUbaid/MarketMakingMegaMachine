# MMMM API Documentation

## Table of Contents
1. [Core Components](#core-components)
2. [API Connector](#api-connector)
3. [Order Handler](#order-handler)
4. [Strategy Base Class](#strategy-base-class)
5. [Configuration Manager](#configuration-manager)
6. [Terminal UI](#terminal-ui)

## Core Components

### ApiConnector
The primary interface for interacting with the HyperLiquid exchange.

```python
class ApiConnector:
    def __init__(self):
        self.wallet: Optional[LocalAccount] = None
        self.wallet_address: Optional[str] = None
        self.exchange: Optional[Exchange] = None
        self.info: Optional[Info] = None
```

#### Key Methods

##### connect_hyperliquid
```python
def connect_hyperliquid(self, wallet_address: str, secret_key: str, use_testnet: bool = False) -> bool
```
Connects to HyperLiquid exchange using provided credentials.

Parameters:
- `wallet_address`: Ethereum wallet address
- `secret_key`: Private key for authentication
- `use_testnet`: Whether to use testnet (default: False)

Returns:
- `bool`: True if connection successful

##### get_balances
```python
def get_balances(self) -> Dict[str, Any]
```
Retrieves all balances (spot and perpetual).

Returns:
```python
{
    "spot": [
        {
            "asset": str,
            "available": float,
            "total": float,
            "in_orders": float
        }
    ],
    "perp": {
        "account_value": float,
        "margin_used": float,
        "position_value": float
    }
}
```

##### get_positions
```python
def get_positions(self) -> List[Dict[str, Any]]
```
Retrieves all open positions.

Returns:
```python
[
    {
        "symbol": str,
        "size": float,
        "entry_price": float,
        "mark_price": float,
        "liquidation_price": float,
        "unrealized_pnl": float,
        "margin_used": float
    }
]
```

##### get_market_data
```python
def get_market_data(self, symbol: str) -> Dict[str, Any]
```
Retrieves market data for a specific symbol.

Parameters:
- `symbol`: Trading pair symbol

Returns:
```python
{
    "mid_price": float,
    "best_bid": float,
    "best_ask": float,
    "order_book": Dict
}
```

### OrderHandler
Handles all order-related operations.

```python
class OrderHandler:
    def __init__(self, exchange: Optional[Exchange], info: Optional[Info]):
        self.exchange = exchange
        self.info = info
        self.api_connector = None
        self.wallet_address = None
```

#### Key Methods

##### market_buy
```python
def market_buy(self, symbol: str, size: float, slippage: float = 0.05) -> Dict[str, Any]
```
Executes a market buy order.

Parameters:
- `symbol`: Trading pair symbol
- `size`: Order size
- `slippage`: Maximum allowed slippage (default: 0.05)

##### limit_buy
```python
def limit_buy(self, symbol: str, size: float, price: float) -> Dict[str, Any]
```
Places a limit buy order.

Parameters:
- `symbol`: Trading pair symbol
- `size`: Order size
- `price`: Limit price

##### scaled_orders
```python
def scaled_orders(self, symbol: str, is_buy: bool, total_size: float, num_orders: int,
                 start_price: float, end_price: float, skew: float = 0,
                 order_type: Dict = None, reduce_only: bool = False) -> Dict[str, Any]
```
Places multiple orders with size distribution.

Parameters:
- `symbol`: Trading pair symbol
- `is_buy`: True for buy orders, False for sell orders
- `total_size`: Total size to distribute
- `num_orders`: Number of orders to place
- `start_price`: Starting price level
- `end_price`: Ending price level
- `skew`: Distribution skew (default: 0)
- `order_type`: Order type parameters
- `reduce_only`: Whether orders are reduce-only

### Strategy Base Class
Base class for all trading strategies.

```python
class TradingStrategy:
    STRATEGY_NAME = "Base Strategy"
    STRATEGY_DESCRIPTION = "Base strategy class"
    STRATEGY_PARAMS = {}
```

#### Key Methods

##### start
```python
def start(self)
```
Starts the strategy execution.

##### stop
```python
def stop(self)
```
Stops the strategy execution.

##### _run_strategy
```python
def _run_strategy(self)
```
Main strategy execution loop (to be implemented by subclasses).

### Configuration Manager
Manages configuration settings.

```python
class ConfigManager:
    def __init__(self, config_file: str = "elysium_config.json"):
        self.config_file = config_file
        self.config = self.load_config()
```

#### Key Methods

##### get
```python
def get(self, key: str, default: Any = None) -> Any
```
Retrieves a configuration value.

##### set
```python
def set(self, key: str, value: Any) -> None
```
Sets a configuration value.

### Terminal UI
Command-line interface for the platform.

```python
class ElysiumTerminalUI(cmd.Cmd):
    def __init__(self, api_connector, order_handler, config_manager):
        self.api_connector = api_connector
        self.order_handler = order_handler
        self.config_manager = config_manager
```

#### Key Commands

##### connect
```python
def do_connect(self, arg)
```
Connects to the exchange.

##### balance
```python
def do_balance(self, arg)
```
Shows account balances.

##### positions
```python
def do_positions(self, arg)
```
Shows open positions.

##### orders
```python
def do_orders(self, arg)
```
Lists open orders.

## Error Handling

All API methods include robust error handling with:
- Connection verification
- Parameter validation
- Response validation
- Exception handling
- Logging

## Rate Limiting

The API connector implements rate limiting to prevent:
- Excessive API calls
- Order spam
- Connection issues

## WebSocket Support

The platform supports WebSocket connections for:
- Real-time market data
- Order updates
- Position updates
- Balance updates

## Authentication

Authentication is handled through:
- Wallet address
- Private key
- API key (if required)

## Constants

```python
MAINNET_API_URL = "https://api.hyperliquid.xyz"
TESTNET_API_URL = "https://api.hyperliquid-testnet.xyz"
LOCAL_API_URL = "http://localhost:3001"
WS_URL = "wss://api.hyperliquid.xyz/ws"
```

## Best Practices

1. **Error Handling**
   - Always check return values
   - Implement proper error handling
   - Log errors appropriately

2. **Rate Limiting**
   - Respect API rate limits
   - Implement backoff strategies
   - Monitor API usage

3. **Security**
   - Never expose private keys
   - Use environment variables
   - Implement proper access control

4. **Performance**
   - Use WebSocket when possible
   - Implement caching
   - Optimize API calls

## Examples

### Basic Connection
```python
api = ApiConnector()
api.connect_hyperliquid(
    wallet_address="0x...",
    secret_key="0x...",
    use_testnet=True
)
```

### Place Orders
```python
order_handler = OrderHandler(api.exchange, api.info)
result = order_handler.limit_buy(
    symbol="BTC",
    size=0.1,
    price=50000
)
```

### Get Market Data
```python
market_data = api.get_market_data("BTC")
print(f"Current mid price: {market_data['mid_price']}")
```

### Monitor Positions
```python
positions = api.get_positions()
for position in positions:
    print(f"Position in {position['symbol']}: {position['size']}")
``` 