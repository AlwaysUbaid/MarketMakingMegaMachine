import logging
import threading
import math
import time
import uuid
from datetime import datetime
from typing import Dict, Optional, Tuple, List, Any

# Import the base strategy class
from strategy_selector import TradingStrategy

# Class-level registry to track active instances per symbol
_active_instances = {}

class UsdhlMarketMaking(TradingStrategy):
    """
    USDHL Market Making Strategy
    
    This strategy places limit orders around the mid price for the USDHL/USDC pair,
    with very tight spreads optimized for stablecoin trading.
    """
    
    # Strategy metadata
    STRATEGY_NAME = "USDHL Market Making"
    STRATEGY_DESCRIPTION = "Limit order market making for stablecoin pair with tight spreads"
    
    # Default parameters with descriptions
    STRATEGY_PARAMS = {
        "symbol": {
            "value": "USDHL/USDC",
            "type": "str",
            "description": "Trading pair symbol"
        },
        "order_amount": {
            "value": 13,  # Order size for each trade
            "type": "float",
            "description": "Size of each order"
        },
        "refresh_time": {
            "value": 3,  # 3 seconds between trades
            "type": "int",
            "description": "Time in seconds between trades"
        },
        "bid_spread": {
            "value": 0.000011,  # 0.005% below mid price
            "type": "float",
            "description": "Spread below mid price for buy orders"
        },
        "ask_spread": {
            "value": 0.000012,  # 0.005% above mid price
            "type": "float",
            "description": "Spread above mid price for sell orders"
        },
        "is_perp": {
            "value": False,
            "type": "bool",
            "description": "Whether to trade perpetual contracts (True) or spot (False)"
        },
        "leverage": {
            "value": 1,
            "type": "int",
            "description": "Leverage to use for perpetual trading (if is_perp is True)"
        }
    }
    
    def __init__(self, api_connector, order_handler, config_manager, params=None):
        """Initialize the market making strategy with custom parameters"""
        super().__init__(api_connector, order_handler, config_manager, params)
        self.symbol = self._get_param_value("symbol") if params else self.STRATEGY_PARAMS["symbol"]["value"]
        self.quote_asset = self.symbol.split('/')[1] if '/' in self.symbol else "USDC"
        self.instance_id = uuid.uuid4().hex[:8]
        if self.symbol not in _active_instances:
            _active_instances[self.symbol] = []
        _active_instances[self.symbol].append(self)
        
        # Extract parameter values
        self.order_amount = self._get_param_value("order_amount")
        self.refresh_time = self._get_param_value("refresh_time")
        self.bid_spread = self._get_param_value("bid_spread")
        self.ask_spread = self._get_param_value("ask_spread")
        self.is_perp = self._get_param_value("is_perp")
        self.leverage = self._get_param_value("leverage")
        
        # Runtime variables
        self.last_tick_time = 0
        self.mid_price = 0
        self.status_message = "Initialized"
        self.status_lock = threading.Lock()
        self.error_count = 0
        self.consecutive_errors = 0
        self.last_successful_trade = 0
        self.running = True
        self.active_orders = {"buy": None, "sell": None}
        
        # Extract asset name from symbol for balance lookup
        self.asset = self.symbol.split('/')[0] if '/' in self.symbol else self.symbol
        
        # Add to __init__
        self._cached_meta = None
        self._cached_meta_time = 0
        self._cached_tick_size = None
        self._cached_size_decimals = None
        self._meta_cache_ttl = 300  # 5 minutes
        
    def _get_param_value(self, param_name):
        """Helper method to extract parameter values"""
        if param_name in self.params:
            if isinstance(self.params[param_name], dict) and "value" in self.params[param_name]:
                return self.params[param_name]["value"]
            return self.params[param_name]
        
        # Fallback to default params
        if param_name in self.STRATEGY_PARAMS:
            if isinstance(self.STRATEGY_PARAMS[param_name], dict) and "value" in self.STRATEGY_PARAMS[param_name]:
                return self.STRATEGY_PARAMS[param_name]["value"]
            return self.STRATEGY_PARAMS[param_name]
        
        self.logger.warning(f"Parameter {param_name} not found, using None")
        return None
    
    def set_status(self, message):
        """Thread-safe status update"""
        with self.status_lock:
            self.status_message = message
            self.logger.info(f"Status: {message}")
    
    def get_status(self):
        """Get current strategy status"""
        with self.status_lock:
            return self.status_message
    
    def get_balances(self) -> Tuple[float, float]:
        """
        Get current asset and quote balances
        
        Returns:
            Tuple of (asset_balance, quote_balance)
        """
        asset_balance = 0
        quote_balance = 0
        
        try:
            # Get asset balance
            if self.is_perp:
                positions = self.order_handler.get_positions()
                for position in positions:
                    if position["symbol"] == self.symbol:
                        asset_balance = position["size"]
                        break
            else:
                balances = self.api_connector.get_balances()
                for balance in balances.get("spot", []):
                    if balance.get("asset") == self.asset:
                        asset_balance = float(balance.get("total", 0))
                        break
            
            # Get quote balance
            try:
                spot_state = self.api_connector.info.spot_user_state(self.api_connector.wallet_address)
                for balance in spot_state.get("balances", []):
                    if balance.get("coin") == self.quote_asset:
                        quote_balance = float(balance.get("total", 0))
                        break
            except:
                balances = self.api_connector.get_balances()
                for balance in balances.get("spot", []):
                    if balance.get("asset") == self.quote_asset:
                        quote_balance = float(balance.get("total", 0))
                        break
                    
            self.logger.info(f"Current balances: {asset_balance} {self.asset}, {quote_balance} {self.quote_asset}")
            return asset_balance, quote_balance
            
        except Exception as e:
            self.logger.error(f"Error getting balances: {str(e)}")
            return 0, 0
    
    def _refresh_meta_cache(self):
        now = time.time()
        if self._cached_meta is None or (now - self._cached_meta_time) > self._meta_cache_ttl:
            try:
                self._cached_meta = self.api_connector.info.meta()
                self._cached_meta_time = now
                # Update tick size and size decimals
                for asset_info in self._cached_meta.get("universe", []):
                    if asset_info.get("name") == self.symbol:
                        self._cached_tick_size = float(asset_info.get("tickSize", 0.00001))
                        self._cached_size_decimals = asset_info.get("szDecimals", 8)
                        break
            except Exception as e:
                self.logger.warning(f"Could not fetch meta for {self.symbol}: {e}")

    def _get_tick_size(self, market_data=None):
        self._refresh_meta_cache()
        if self._cached_tick_size is not None:
            return self._cached_tick_size
        return 0.00001  # fallback

    def _format_price_buy(self, price, tick_size):
        # Always round DOWN to nearest tick for buy
        ticks = math.floor(price / tick_size)
        rounded = ticks * tick_size
        decimals = max(0, -int(math.floor(math.log10(tick_size)))) if tick_size < 1 else 0
        return round(rounded, decimals)

    def _format_price_sell(self, price, tick_size):
        # Always round UP to nearest tick for sell
        ticks = math.ceil(price / tick_size)
        rounded = ticks * tick_size
        decimals = max(0, -int(math.floor(math.log10(tick_size)))) if tick_size < 1 else 0
        return round(rounded, decimals)

    def _place_buy_order(self, market_data):
        """Place a buy limit order with full response logging and min size check"""
        try:
            mid_price = float(market_data.get("mid_price", 0))
            if mid_price <= 0:
                self.logger.error("Invalid mid price for buy order")
                return False

            tick_size = self._get_tick_size(market_data)
            min_order_size = getattr(self, '_cached_min_order_size', 0.00001)
            if hasattr(self, '_cached_meta') and self._cached_meta:
                for asset_info in self._cached_meta.get("universe", []):
                    if asset_info.get("name") == self.symbol:
                        min_order_size = float(asset_info.get("minSz", 0.00001))
                        self._cached_min_order_size = min_order_size
                        break

            order_size = self._format_size(self.order_amount)
            if order_size < min_order_size:
                self.logger.warning(f"Buy order size {order_size} is below minimum {min_order_size}, skipping.")
                return False

            buy_price = self._format_price_buy(mid_price * (1 - self.bid_spread), tick_size)

            if self.is_perp:
                result = self.order_handler.perp_limit_buy(self.symbol, order_size, buy_price, self.leverage)
            else:
                result = self.order_handler.limit_buy(self.symbol, order_size, buy_price)

            self.logger.info(f"Buy order response: {result}")

            if result and result.get("status") == "ok":
                statuses = result.get("response", {}).get("data", {}).get("statuses", [])
                for status in statuses:
                    if "resting" in status:
                        self.logger.info(f"Placed buy limit order at {buy_price} for {order_size} {self.asset} (order open)")
                        self.active_orders["buy"] = status["resting"].get("oid")
                        return True
                    elif "filled" in status:
                        self.logger.info(f"Buy order immediately filled at {buy_price} for {order_size} {self.asset}")
                        return False
                    elif "error" in status:
                        self.logger.error(f"Buy order error: {status['error']}")
                        return False
                self.logger.warning("Buy order not resting, not filled, not error. Check response.")
                return False
            else:
                error_msg = result.get("message", "Unknown error") if result else "No result"
                self.logger.error(f"Failed to place buy limit order: {error_msg}")
                return False
        except Exception as e:
            self.logger.error(f"Error placing buy order: {str(e)}")
            return False

    def _place_sell_order(self, market_data, available_balance):
        """Place a sell limit order with full response logging and min size check"""
        try:
            mid_price = float(market_data.get("mid_price", 0))
            if mid_price <= 0:
                self.logger.error("Invalid mid price for sell order")
                return False

            tick_size = self._get_tick_size(market_data)
            min_order_size = getattr(self, '_cached_min_order_size', 0.00001)
            if hasattr(self, '_cached_meta') and self._cached_meta:
                for asset_info in self._cached_meta.get("universe", []):
                    if asset_info.get("name") == self.symbol:
                        min_order_size = float(asset_info.get("minSz", 0.00001))
                        self._cached_min_order_size = min_order_size
                        break

            order_size = min(self._format_size(self.order_amount), self._format_size(available_balance))
            if order_size < min_order_size:
                self.logger.warning(f"Sell order size {order_size} is below minimum {min_order_size}, skipping.")
                return False

            sell_price = self._format_price_sell(mid_price * (1 + self.ask_spread), tick_size)

            if self.is_perp:
                result = self.order_handler.perp_limit_sell(self.symbol, order_size, sell_price, self.leverage)
            else:
                result = self.order_handler.limit_sell(self.symbol, order_size, sell_price)

            self.logger.info(f"Sell order response: {result}")

            if result and result.get("status") == "ok":
                statuses = result.get("response", {}).get("data", {}).get("statuses", [])
                for status in statuses:
                    if "resting" in status:
                        self.logger.info(f"Placed sell limit order at {sell_price} for {order_size} {self.asset} (order open)")
                        self.active_orders["sell"] = status["resting"].get("oid")
                        return True
                    elif "filled" in status:
                        self.logger.info(f"Sell order immediately filled at {sell_price} for {order_size} {self.asset}")
                        return False
                    elif "error" in status:
                        self.logger.error(f"Sell order error: {status['error']}")
                        return False
                self.logger.warning("Sell order not resting, not filled, not error. Check response.")
                return False
            else:
                error_msg = result.get("message", "Unknown error") if result else "No result"
                self.logger.error(f"Failed to place sell limit order: {error_msg}")
                return False
        except Exception as e:
            self.logger.error(f"Error placing sell order: {str(e)}")
            return False

    def _cancel_active_orders(self):
        """Cancel all active orders"""
        try:
            for side, order_id in self.active_orders.items():
                if order_id:
                    self.order_handler.cancel_order(self.symbol, order_id)
                    self.logger.info(f"Cancelled {side} order {order_id}")
            self.active_orders = {"buy": None, "sell": None}
        except Exception as e:
            self.logger.error(f"Error cancelling orders: {str(e)}")

    def _run_strategy(self):
        """Main strategy execution loop"""
        self.set_status("Starting USDHL market making strategy")
        
        # Set leverage if using perpetual
        if self.is_perp and self.leverage > 1:
            try:
                self.order_handler._set_leverage(self.symbol, self.leverage)
                self.logger.info(f"Set leverage to {self.leverage}x for {self.symbol}")
            except Exception as e:
                self.logger.error(f"Failed to set leverage: {str(e)}")
        
        # Initial check of balances
        asset_balance, quote_balance = self.get_balances()
        self.logger.info(f"Starting with: {asset_balance} {self.asset}, {quote_balance} {self.quote_asset}")
        
        # Main strategy variables
        self.running = True
        backoff_time = 0
        
        # Main strategy loop
        try:
            while not self.stop_requested and self.running:
                current_time = time.time()
                
                # If we're in backoff mode, wait before trying again
                if backoff_time > current_time:
                    time.sleep(0.1)
                    continue
                
                # Check if it's time to refresh orders
                if (current_time - self.last_tick_time) >= self.refresh_time:
                    # Get latest market data
                    market_data = self.api_connector.get_market_data(self.symbol)
                    if not market_data or "mid_price" not in market_data:
                        self.logger.warning("Could not get market data, skipping iteration")
                        continue
                    
                    # Get latest balances
                    asset_balance, quote_balance = self.get_balances()
                    
                    # Cancel existing orders
                    self._cancel_active_orders()
                    
                    # Place new orders
                    buy_success = self._place_buy_order(market_data)
                    sell_success = self._place_sell_order(market_data, asset_balance)
                    
                    # Update tracking variables
                    if buy_success and sell_success:
                        self.set_status(f"Placed orders around {market_data['mid_price']}")
                        self.last_tick_time = current_time
                        self.consecutive_errors = 0
                    else:
                        self.consecutive_errors += 1
                        self.error_count += 1
                        
                        # Implement backoff if we keep failing
                        if self.consecutive_errors > 3:
                            backoff_seconds = min(30, 2 ** (self.consecutive_errors - 3))
                            backoff_time = current_time + backoff_seconds
                            self.set_status(f"Order placement issues, backing off for {backoff_seconds}s")
                
                # Sleep to avoid excessive CPU usage
                time.sleep(0.01)
                
        except Exception as e:
            self.logger.error(f"Error in strategy loop: {str(e)}", exc_info=True)
            self.set_status(f"Error: {str(e)}")
        
        finally:
            # Cancel any remaining orders
            self._cancel_active_orders()
            self.running = False
            self.set_status("Market making strategy stopped")

    def get_performance_metrics(self):
        """Get performance metrics for the strategy"""
        try:
            asset_balance, quote_balance = self.get_balances()
            market_data = self.api_connector.get_market_data(self.symbol)
            
            metrics = {
                "symbol": self.symbol,
                "asset_balance": asset_balance,
                "quote_balance": quote_balance,
                "mid_price": market_data.get("mid_price", 0),
                "bid_spread": self.bid_spread,
                "ask_spread": self.ask_spread,
                "order_size": self.order_amount,
                "errors": self.error_count,
                "last_trade": datetime.fromtimestamp(self.last_successful_trade).strftime("%Y-%m-%d %H:%M:%S") if self.last_successful_trade else "Never"
            }
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"Error calculating metrics: {str(e)}")
            return {
                "symbol": self.symbol,
                "error": str(e)
            }

    def __del__(self):
        """Cleanup method"""
        self.running = False
        self._cancel_active_orders()
        self.set_status("Instance cleaned up")

    def _get_size_decimals(self):
        self._refresh_meta_cache()
        if self._cached_size_decimals is not None:
            return self._cached_size_decimals
        return 8

    def _format_size(self, size):
        """Format the order size to the allowed number of decimals."""
        decimals = self._get_size_decimals()
        return round(size, decimals) 