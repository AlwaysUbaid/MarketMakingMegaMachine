import logging
import threading
import math
import time
from datetime import datetime
from typing import Dict, Optional, Tuple, List, Any

# Import the base strategy class
from strategy_selector import TradingStrategy

class UsolMarketMaking(TradingStrategy):
    """
    USOL Market Making Strategy
    
    This strategy places buy and sell orders around the mid price,
    aiming to profit from the spread between bids and asks.
    """
    
    # Strategy metadata
    STRATEGY_NAME = "Usol Market Making"
    STRATEGY_DESCRIPTION = "Places buy and sell orders around the mid price to earn the spread"
    
    # Default parameters with descriptions
    STRATEGY_PARAMS = {
        "symbol": {
            "value": "USOL/USDC",
            "type": "str",
            "description": "Trading pair symbol"
        },
        "bid_spread": {
            "value": 0.0011,  # 0.1%
            "type": "float",
            "description": "Spread below mid price for buy orders (as a decimal)"
        },
        "ask_spread": {
            "value": 0.0012, 
            "type": "float",
            "description": "Spread above mid price for sell orders (as a decimal)"
        },
        "order_amount": {
            "value": 0.065,  # 0.065 USOL
            "type": "float",
            "description": "Size of each order"
        },
        "refresh_time": {
            "value": 10,  # 10 seconds
            "type": "int",
            "description": "Time in seconds between order refresh"
        },
        "order_max_age": {
            "value": 30,  # 30 seconds default
            "type": "int",
            "description": "Maximum time in seconds before unfilled orders are cancelled and replaced"
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
        
        # Extract parameter values
        self.symbol = self._get_param_value("symbol")
        self.bid_spread = self._get_param_value("bid_spread")
        self.ask_spread = self._get_param_value("ask_spread")
        self.order_amount = self._get_param_value("order_amount")
        self.refresh_time = self._get_param_value("refresh_time")
        self.order_max_age = self._get_param_value("order_max_age")
        self.is_perp = self._get_param_value("is_perp")
        self.leverage = self._get_param_value("leverage")
        
        # Runtime variables
        self.last_tick_time = 0
        self.mid_price = 0
        self.active_buy_order_id = None
        self.active_sell_order_id = None
        self.active_buy_order_time = None  
        self.active_sell_order_time = None  
        self.status_message = "Initialized"
        self.status_lock = threading.Lock()
        self.prev_mid_price = None
        self.last_order_update = 0
        self.error_count = 0
        self.consecutive_errors = 0
        self.last_successful_placement = 0
        self.last_cancel_time = 0  # Track when we last cancelled all orders
        self.auto_cancel_thread = None
        self.auto_cancel_active = False
        self.auto_cancel_interval = 15  # Default, can be set via param if desired
        
        # Extract asset name from symbol for balance lookup
        self.asset = self.symbol.split('/')[0] if '/' in self.symbol else self.symbol
        self.quote_asset = self.symbol.split('/')[1] if '/' in self.symbol else "USDC"
        
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
                        asset_balance = float(balance.get("total", 0))  # Use total instead of available
                        break
            
            # Get quote balance - use spot_state directly for accurate balance
            try:
                spot_state = self.api_connector.info.spot_user_state(self.api_connector.wallet_address)
                for balance in spot_state.get("balances", []):
                    if balance.get("coin") == self.quote_asset:
                        quote_balance = float(balance.get("total", 0))  # Use total instead of available
                        break
            except:
                # Fallback to regular balance method
                balances = self.api_connector.get_balances()
                for balance in balances.get("spot", []):
                    if balance.get("asset") == self.quote_asset:
                        quote_balance = float(balance.get("total", 0))  # Use total instead of available
                        break
                    
            self.logger.info(f"Current balances: {asset_balance} {self.asset}, {quote_balance} {self.quote_asset}")
            return asset_balance, quote_balance
            
        except Exception as e:
            self.logger.error(f"Error getting balances: {str(e)}")
            # If we can't get balances, assume we have funds to continue trading
            return 0, 99.0  # Default to $99 if we can't get actual balance
    
    def _check_order_result(self, result, side_str):
        """
        Check order result and handle errors
        
        Args:
            result: Order result dictionary
            side_str: String indicating order side ("Buy" or "Sell")
            
        Returns:
            Tuple of (success, order_id, error_message)
        """
        if not result:
            return False, None, "No result returned"
            
        if result["status"] != "ok":
            error_msg = result.get("message", "Unknown error")
            if "Insufficient spot balance" in error_msg:
                self.logger.error(f"{side_str} order error: {error_msg}")
                self._trigger_auto_cancel_all()
            return False, None, error_msg
            
        if "response" not in result or "data" not in result["response"] or "statuses" not in result["response"]["data"]:
            return False, None, "Invalid response format"
            
        # Check for specific error messages in response
        for status in result["response"]["data"]["statuses"]:
            if "error" in status:
                error_msg = status["error"]
                self.logger.error(f"{side_str} order error: {error_msg}")
                if "Insufficient spot balance" in error_msg:
                    self._trigger_auto_cancel_all()
                return False, None, error_msg
            
            if "resting" in status:
                self._stop_auto_cancel_all()
                order_id = status["resting"]["oid"]
                return True, order_id, None
                
            if "filled" in status:
                # Order was immediately filled
                self._stop_auto_cancel_all()
                filled = status["filled"]
                order_id = filled.get("oid", 0)
                self.logger.info(f"{side_str} order immediately filled: {filled.get('totalSz', 0)} @ {filled.get('avgPx', 0)}")
                return True, order_id, None
                
        return False, None, "No resting order or specific error found in response"
    
    def _place_buy_order(self, market_data):
        """
        Place a buy order at an appropriate price
        
        Args:
            market_data: Dictionary with market data including best_bid, best_ask
            
        Returns:
            Tuple of (success, order_id)
        """
        try:
            tick_size = self._get_tick_size(market_data)
            best_bid = market_data.get("best_bid", 0)
            best_ask = market_data.get("best_ask", 0)
            
            if not best_bid or not best_ask:
                self.logger.error("Missing market data, cannot place buy order")
                return False, None
            
            # Calculate buy price as spread away from mid price
            # Ensure it's below best ask to avoid crossing book
            mid_price = (best_bid + best_ask) / 2
            bid_price = mid_price * (1 - self.bid_spread)
            bid_price = min(bid_price, best_ask - tick_size)  # Ensure below best ask
            bid_price = max(bid_price, 0.0000001)  # Ensure positive price
            
            # Format price to valid tick size
            bid_price = self._format_price(bid_price, tick_size)
            
            # Use exact order amount
            buy_size = self.order_amount
            
            self.logger.info(f"Placing buy order: {buy_size} {self.symbol} @ {bid_price}")
            
            # Place appropriate order type
            if self.is_perp:
                result = self.order_handler.perp_limit_buy(self.symbol, buy_size, bid_price, self.leverage)
            else:
                result = self.order_handler.limit_buy(self.symbol, buy_size, bid_price)
            
            # Check result
            success, order_id, error_msg = self._check_order_result(result, "Buy")
            if success:
                self.active_buy_order_id = order_id
                self.active_buy_order_time = time.time()
                self.logger.info(f"Successfully placed buy order ID {order_id} at {bid_price}")
                return True, order_id
            else:
                self.logger.error(f"Failed to place buy order: {error_msg}")
                return False, None
                
        except Exception as e:
            self.logger.error(f"Error placing buy order: {str(e)}")
            return False, None
    
    def _place_sell_order(self, market_data, available_balance):
        """
        Place a sell order at an appropriate price
        
        Args:
            market_data: Dictionary with market data including best_bid, best_ask
            available_balance: Available balance of the asset to sell
            
        Returns:
            Tuple of (success, order_id)
        """
        try:
            tick_size = self._get_tick_size(market_data)
            best_bid = market_data.get("best_bid", 0)
            best_ask = market_data.get("best_ask", 0)
            
            if not best_bid or not best_ask:
                self.logger.error("Missing market data, cannot place sell order")
                return False, None
            
            # Calculate appropriate sell size based on available balance
            sell_size = min(self.order_amount, available_balance)
            
            # Check if we have enough to sell
            if sell_size < 0.00001:  # Minimum size to avoid errors
                self.logger.warning(f"Available balance too small to sell: {available_balance}")
                return False, None
            
            # Calculate sell price as spread away from mid price
            # Ensure it's above best bid to avoid crossing book
            mid_price = (best_bid + best_ask) / 2
            ask_price = mid_price * (1 + self.ask_spread)
            ask_price = max(ask_price, best_bid + tick_size)  # Ensure above best bid
            
            # Format price to valid tick size
            ask_price = self._format_price(ask_price, tick_size)
            
            self.logger.info(f"Placing sell order: {sell_size} {self.symbol} @ {ask_price}")
            
            # Place appropriate order type
            if self.is_perp:
                result = self.order_handler.perp_limit_sell(self.symbol, sell_size, ask_price, self.leverage)
            else:
                result = self.order_handler.limit_sell(self.symbol, sell_size, ask_price)
            
            # Check result
            success, order_id, error_msg = self._check_order_result(result, "Sell")
            if success:
                self.active_sell_order_id = order_id
                self.active_sell_order_time = time.time()
                self.logger.info(f"Successfully placed sell order ID {order_id} at {ask_price}")
                return True, order_id
            else:
                self.logger.error(f"Failed to place sell order: {error_msg}")
                return False, None
                
        except Exception as e:
            self.logger.error(f"Error placing sell order: {str(e)}")
            return False, None
            
    def _check_orders_status(self):
        """
        Check if active orders are still open, filled, or disappeared
        Updates internal order tracking
        
        Returns:
            Tuple of (buy_still_active, sell_still_active)
        """
        buy_still_active = False
        sell_still_active = False
        
        try:
            # Get current open orders
            open_orders = self.order_handler.get_open_orders(self.symbol)
            
            # Check buy order status
            if self.active_buy_order_id:
                buy_still_active = any(order.get("oid") == self.active_buy_order_id for order in open_orders)
                
                if not buy_still_active:
                    self.logger.info(f"Buy order {self.active_buy_order_id} is no longer open (likely filled or cancelled)")
                    self.active_buy_order_id = None
                    self.active_buy_order_time = None
            
            # Check sell order status
            if self.active_sell_order_id:
                sell_still_active = any(order.get("oid") == self.active_sell_order_id for order in open_orders)
                
                if not sell_still_active:
                    self.logger.info(f"Sell order {self.active_sell_order_id} is no longer open (likely filled or cancelled)")
                    self.active_sell_order_id = None
                    self.active_sell_order_time = None
                    
            return buy_still_active, sell_still_active
            
        except Exception as e:
            self.logger.error(f"Error checking order status: {str(e)}")
            return False, False
    
    def _run_strategy(self):
        """Main strategy execution loop"""
        self.set_status("Starting market making strategy")
        
        # Verify exchange connection
        if not self.api_connector.exchange or not self.order_handler.exchange:
            self.set_status("Error: Exchange connection is not active. Please connect first.")
            self.logger.error("Exchange connection not active when starting strategy")
            self.running = False
            return
        
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
        last_order_check = 0
        
        # Main strategy loop
        try:
            while not self.stop_requested and self.running:
                current_time = time.time()
                
                # If we're in backoff mode, wait before trying again
                if backoff_time > current_time:
                    time.sleep(0.1)
                    continue
                
                # Check if it's time to cancel all orders based on the timer
                if (current_time - self.last_cancel_time) > self.order_max_age:
                    self.logger.info(f"Cancelling all orders after {self.order_max_age}s timeout")
                    self.order_handler.cancel_all_orders(self.symbol)
                    self.active_buy_order_id = None
                    self.active_sell_order_id = None
                    self.active_buy_order_time = None
                    self.active_sell_order_time = None
                    self.last_cancel_time = current_time
                    
                    # Get fresh market data after cancellation
                    market_data = self.api_connector.get_market_data(self.symbol)
                    if "error" in market_data:
                        self.set_status(f"Error getting market data after cancel: {market_data['error']}")
                        time.sleep(1)
                    else:
                        # Update mid price
                        if "mid_price" in market_data:
                            self.mid_price = market_data["mid_price"]
                        elif "best_bid" in market_data and "best_ask" in market_data:
                            best_bid = market_data["best_bid"]
                            best_ask = market_data["best_ask"]
                            self.mid_price = (best_bid + best_ask) / 2
                        
                        # Get latest balances
                        asset_balance, quote_balance = self.get_balances()
                        
                        # Place new orders
                        if quote_balance > 1.0:
                            self._place_buy_order(market_data)
                            
                        if asset_balance > 0.00001:
                            self._place_sell_order(market_data, asset_balance)
                
                # Check if it's time to refresh
                refresh_needed = (current_time - self.last_tick_time) >= self.refresh_time
                should_check_orders = (current_time - last_order_check) >= 1  # Check order status frequently
                
                # Check order status more frequently than placing new orders
                if should_check_orders:
                    buy_active, sell_active = self._check_orders_status()
                    last_order_check = current_time
                
                # Full refresh cycle
                if refresh_needed:
                    # 1. Get market data
                    market_data = self.api_connector.get_market_data(self.symbol)
                    if "error" in market_data:
                        self.set_status(f"Error getting market data: {market_data['error']}")
                        time.sleep(1)
                        continue
                    
                    # 2. Update mid price tracking
                    if "mid_price" in market_data:
                        self.mid_price = market_data["mid_price"]
                    elif "best_bid" in market_data and "best_ask" in market_data:
                        best_bid = market_data["best_bid"]
                        best_ask = market_data["best_ask"]
                        self.mid_price = (best_bid + best_ask) / 2
                    else:
                        self.set_status("No price data available")
                        time.sleep(1)
                        continue
                    
                    # 3. Get latest balances
                    asset_balance, quote_balance = self.get_balances()
                    
                    # 4. Refresh orders only if needed based on current status
                    success = True
                    
                    # No active buy order and we have quote balance - place buy
                    if not self.active_buy_order_id and quote_balance > 1.0:  # Ensure we have at least $1 to trade
                        buy_success, _ = self._place_buy_order(market_data)
                        success = success and buy_success
                    
                    # No active sell order and we have asset balance - place sell
                    if not self.active_sell_order_id and asset_balance > 0.00001:  # Small minimum threshold
                        sell_success, _ = self._place_sell_order(market_data, asset_balance)
                        success = success and sell_success
                    
                    # Update tracking variables
                    if success:
                        self.set_status(f"Orders managed successfully at {self.mid_price}")
                        self.last_tick_time = current_time
                        self.last_order_update = current_time
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
            self._stop_auto_cancel_all()
            self._cancel_active_orders()
            self.running = False
            self.set_status("Market making strategy stopped")
    
    def _cancel_active_orders(self):
        """Cancel all active orders for this strategy"""
        try:
            if self.active_buy_order_id:
                self.order_handler.cancel_order(self.symbol, self.active_buy_order_id)
                self.logger.info(f"Cancelled buy order {self.active_buy_order_id}")
                self.active_buy_order_id = None
                self.active_buy_order_time = None
                
            if self.active_sell_order_id:
                self.order_handler.cancel_order(self.symbol, self.active_sell_order_id)
                self.logger.info(f"Cancelled sell order {self.active_sell_order_id}")
                self.active_sell_order_id = None
                self.active_sell_order_time = None
                
        except Exception as e:
            self.logger.error(f"Error cancelling orders: {str(e)}")
    
    def _get_tick_size(self, market_data=None):
        """
        Get minimum price increment (tick size) for the symbol
        
        Args:
            market_data: Optional market data to use for inference
            
        Returns:
            float: Tick size
        """
        try:
            # Try to get directly from exchange metadata
            if self.api_connector and self.api_connector.info:
                meta = self.api_connector.info.meta()
                
                # Look for the symbol directly
                for asset_info in meta.get("universe", []):
                    if asset_info.get("name") == self.symbol:
                        if "tickSize" in asset_info:
                            return float(asset_info["tickSize"])
                
                # For spot assets in format XXX/YYY, try the base asset
                base_symbol = self.symbol.split('/')[0] if '/' in self.symbol else self.symbol
                for asset_info in meta.get("universe", []):
                    if asset_info.get("name") == base_symbol:
                        if "tickSize" in asset_info:
                            return float(asset_info["tickSize"])
            
            # If we have market data, try to infer from it
            if market_data and "order_book" in market_data:
                order_book = market_data["order_book"]
                
                # Extract price levels from order book
                bid_prices = []
                ask_prices = []
                
                if "levels" in order_book and len(order_book["levels"]) >= 2:
                    # Extract bid prices
                    for bid in order_book["levels"][0]:
                        if "px" in bid:
                            bid_prices.append(float(bid["px"]))
                    
                    # Extract ask prices
                    for ask in order_book["levels"][1]:
                        if "px" in ask:
                            ask_prices.append(float(ask["px"]))
                    
                    # Find minimum difference between adjacent prices
                    if len(bid_prices) >= 2:
                        bid_prices.sort()
                        diff = min(abs(bid_prices[i] - bid_prices[i-1]) for i in range(1, len(bid_prices)))
                        if diff > 0:
                            return diff
                    
                    if len(ask_prices) >= 2:
                        ask_prices.sort()
                        diff = min(abs(ask_prices[i] - ask_prices[i-1]) for i in range(1, len(ask_prices)))
                        if diff > 0:
                            return diff
            
            # Default tick sizes based on price range
            if self.mid_price >= 10000:  # BTC-like
                return 0.5
            elif self.mid_price >= 1000:
                return 0.1
            elif self.mid_price >= 100:
                return 0.01
            elif self.mid_price >= 10:
                return 0.001
            elif self.mid_price >= 1:
                return 0.0001
            else:
                return 0.00001
                
        except Exception as e:
            self.logger.warning(f"Error determining tick size: {str(e)}")
            return 0.00001  # Very conservative default
    
    def _format_price(self, price, tick_size):
        """
        Format price to comply with exchange tick size
        
        Args:
            price: Original price
            tick_size: Minimum price increment
            
        Returns:
            float: Properly formatted price
        """
        if tick_size <= 0:
            return round(price, 8)  # Default to 8 decimal places
        
        # Round to nearest tick size
        rounded_price = round(price / tick_size) * tick_size
        
        # Determine appropriate decimal places
        if tick_size >= 1:
            decimal_places = 0
        else:
            decimal_places = -int(math.floor(math.log10(tick_size)))
        
        # Format with appropriate precision
        return round(rounded_price, decimal_places)
    
    def get_performance_metrics(self):
        """
        Get performance metrics for the strategy
        
        Returns:
            dict: Performance metrics
        """
        try:
            asset_balance, quote_balance = self.get_balances()

            # NEW: Calculate order ages
            current_time = time.time()
            buy_order_age = (current_time - self.active_buy_order_time) if self.active_buy_order_time else 0
            sell_order_age = (current_time - self.active_sell_order_time) if self.active_sell_order_time else 0
            
            
            metrics = {
                "symbol": self.symbol,
                "mid_price": self.mid_price,
                "has_buy_order": self.active_buy_order_id is not None,
                "has_sell_order": self.active_sell_order_id is not None,
                "buy_order_age": f"{buy_order_age:.1f}s" if buy_order_age > 0 else "N/A",  # NEW: Add this line
                "sell_order_age": f"{sell_order_age:.1f}s" if sell_order_age > 0 else "N/A",  # NEW: Add this line
                "order_max_age": f"{self.order_max_age}s",  # NEW: Add this line
                "asset_balance": asset_balance,
                "quote_balance": quote_balance,
                "order_size": self.order_amount,
                "errors": self.error_count,
                "last_update": datetime.fromtimestamp(self.last_tick_time).strftime("%Y-%m-%d %H:%M:%S") if self.last_tick_time else "Never"
            }
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"Error calculating metrics: {str(e)}")
            return {
                "symbol": self.symbol,
                "error": str(e)
            }

    def _trigger_auto_cancel_all(self):
        if not self.auto_cancel_active:
            self.logger.warning("Triggering auto-cancel-all routine due to insufficient spot balance error.")
            self.order_handler.cancel_all_orders(self.symbol)
            self.auto_cancel_active = True
            self.auto_cancel_thread = threading.Thread(target=self._auto_cancel_all_loop, daemon=True)
            self.auto_cancel_thread.start()

    def _auto_cancel_all_loop(self):
        while self.auto_cancel_active and self.running:
            self.logger.info(f"[AutoCancel] Cancelling all orders every {self.auto_cancel_interval}s due to insufficient spot balance error.")
            self.order_handler.cancel_all_orders(self.symbol)
            for _ in range(self.auto_cancel_interval * 10):
                if not self.auto_cancel_active or not self.running:
                    break
                time.sleep(0.1)

    def _stop_auto_cancel_all(self):
        if self.auto_cancel_active:
            self.logger.info("Stopping auto-cancel-all routine (order placed or strategy stopped).")
            self.auto_cancel_active = False