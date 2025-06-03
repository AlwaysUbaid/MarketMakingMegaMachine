import logging
import threading
import math
import time
from datetime import datetime
from typing import Dict, Optional, Tuple, List, Any

# Import the base strategy class
from strategy_selector import TradingStrategy
from volatility_spread_enhancement import VolatilitySpreadManager

class DynaVolaStrategy(TradingStrategy):
    """
    Dynamic Volatility Market Making Strategy
    
    This strategy places buy and sell orders around the mid price,
    with spreads dynamically adjusted based on market volatility.
    """
    
    # Strategy metadata
    STRATEGY_NAME = "Dynamic Volatility Market Making"
    STRATEGY_DESCRIPTION = "Places orders with dynamic spreads based on market volatility"
    
    # Default parameters with descriptions
    STRATEGY_PARAMS = {
        "symbol": {
            "value": "UBTC/USDC",
            "type": "str",
            "description": "Trading pair symbol"
        },
        "bid_spread": {
            "value": 0.00011,  # 0.1%
            "type": "float",
            "description": "Base spread below mid price for buy orders (as a decimal)"
        },
        "ask_spread": {
            "value": 0.00012,  # 0.1%
            "type": "float",
            "description": "Base spread above mid price for sell orders (as a decimal)"
        },
        "order_amount": {
            "value": 0.00013,
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
            "description": "Maximum time in seconds before unfilled orders are cancelled"
        },
        "price_deviation_threshold": {
            "value": 0.005,  # 0.5% default
            "type": "float",
            "description": "Cancel orders when price deviates by this percentage"
        },
        "max_order_distance": {
            "value": 0.01,  # 1% default
            "type": "float", 
            "description": "Maximum distance from current price to keep orders active"
        },
        "volatility_window": {
            "value": 300,  # 5 minutes
            "type": "int",
            "description": "Time window (in seconds) for volatility calculation"
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
        self.price_deviation_threshold = self._get_param_value("price_deviation_threshold")
        self.max_order_distance = self._get_param_value("max_order_distance")
        self.volatility_window = self._get_param_value("volatility_window")
        self.is_perp = self._get_param_value("is_perp")
        self.leverage = self._get_param_value("leverage")
        
        # Store original spreads for reference
        self.original_bid_spread = self.bid_spread
        self.original_ask_spread = self.ask_spread
        
        # Initialize volatility spread manager
        self.spread_manager = VolatilitySpreadManager(
            base_bid_spread=self.bid_spread,
            base_ask_spread=self.ask_spread,
            volatility_window=self.volatility_window,
            price_window=200
        )
        self.logger.info("Dynamic spreads enabled with volatility-based adjustments")
        
        # Runtime variables
        self.last_tick_time = 0
        self.mid_price = 0
        self.active_buy_order_id = None
        self.active_sell_order_id = None
        self.active_buy_order_time = None  
        self.active_sell_order_time = None  
        self.active_buy_order_price = None  # Store the actual order price
        self.active_sell_order_price = None  # Store the actual order price
        self.status_message = "Initialized"
        self.status_lock = threading.Lock()
        self.prev_mid_price = None
        self.last_order_update = 0
        self.error_count = 0
        self.consecutive_errors = 0
        self.last_successful_placement = 0
        
        # Extract asset name from symbol for balance lookup
        self.asset = self.symbol.split('/')[0] if '/' in self.symbol else self.symbol
        self.quote_asset = self.symbol.split('/')[1] if '/' in self.symbol else "USDC"
        
        # Auto-cancellation variables
        self.auto_cancel_thread = None
        self.auto_cancel_running = False
        self.auto_cancel_stop_event = threading.Event()
        self.last_cancel_all_time = 0
        self.emergency_sell_done = False
        self.strategy_start_time = 0
        
    def _check_and_cancel_orders(self, market_data):
        """Check if orders need to be cancelled based on age or price deviation"""
        current_time = time.time()
        need_cancel_buy = False
        need_cancel_sell = False
        
        # Get current market midpoint
        if "mid_price" in market_data:
            current_mid_price = market_data["mid_price"]
        elif "best_bid" in market_data and "best_ask" in market_data:
            current_mid_price = (market_data["best_bid"] + market_data["best_ask"]) / 2
        else:
            self.logger.warning("Cannot check price deviation: no price data available")
            return False, False
        
        # Check buy order for cancellation
        if self.active_buy_order_id and self.active_buy_order_time:
            cancel_buy_reason = None
            
            # 1. Check age-based cancellation
            order_age = current_time - self.active_buy_order_time
            if order_age > self.order_max_age:
                cancel_buy_reason = f"exceeded max age of {self.order_max_age}s (current age: {order_age:.1f}s)"
            
            # 2. Check price deviation-based cancellation (if we know the order price)
            elif self.active_buy_order_price:
                # Calculate current ideal buy price
                current_buy_price = current_mid_price * (1 - self.bid_spread)
                
                # Calculate price deviation percentage
                deviation = abs(current_buy_price - self.active_buy_order_price) / self.active_buy_order_price
                
                # Cancel if deviation exceeds threshold
                if deviation > self.price_deviation_threshold:
                    cancel_buy_reason = f"price deviation {deviation:.2%} exceeds threshold {self.price_deviation_threshold:.2%}"
                
                # 3. Check distance from current price (optional)
                elif self.active_buy_order_price < current_mid_price * (1 - self.max_order_distance):
                    cancel_buy_reason = f"order price {self.active_buy_order_price} too far below current mid price {current_mid_price}"
            
            # Execute cancellation if needed
            if cancel_buy_reason:
                self.logger.info(f"Cancelling buy order {self.active_buy_order_id}: {cancel_buy_reason}")
                try:
                    result = self.order_handler.cancel_order(self.symbol, self.active_buy_order_id)
                    if result and result.get("status") == "ok":
                        self.logger.info(f"Buy order {self.active_buy_order_id} cancelled successfully")
                    else:
                        self.logger.warning(f"Failed to cancel buy order {self.active_buy_order_id}: {result}")
                except Exception as e:
                    self.logger.error(f"Error cancelling buy order {self.active_buy_order_id}: {str(e)}")
                finally:
                    # Clear order tracking
                    self.active_buy_order_id = None
                    self.active_buy_order_time = None
                    self.active_buy_order_price = None
                    need_cancel_buy = True
        
        # Check sell order for cancellation (similar logic)
        if self.active_sell_order_id and self.active_sell_order_time:
            cancel_sell_reason = None
            
            # 1. Check age-based cancellation
            order_age = current_time - self.active_sell_order_time
            if order_age > self.order_max_age:
                cancel_sell_reason = f"exceeded max age of {self.order_max_age}s (current age: {order_age:.1f}s)"
            
            # 2. Check price deviation-based cancellation (if we know the order price)
            elif self.active_sell_order_price:
                # Calculate current ideal sell price
                current_sell_price = current_mid_price * (1 + self.ask_spread)
                
                # Calculate price deviation percentage
                deviation = abs(current_sell_price - self.active_sell_order_price) / self.active_sell_order_price
                
                # Cancel if deviation exceeds threshold
                if deviation > self.price_deviation_threshold:
                    cancel_sell_reason = f"price deviation {deviation:.2%} exceeds threshold {self.price_deviation_threshold:.2%}"
                
                # 3. Check distance from current price (optional)
                elif self.active_sell_order_price > current_mid_price * (1 + self.max_order_distance):
                    cancel_sell_reason = f"order price {self.active_sell_order_price} too far above current mid price {current_mid_price}"
            
            # Execute cancellation if needed
            if cancel_sell_reason:
                self.logger.info(f"Cancelling sell order {self.active_sell_order_id}: {cancel_sell_reason}")
                try:
                    result = self.order_handler.cancel_order(self.symbol, self.active_sell_order_id)
                    if result and result.get("status") == "ok":
                        self.logger.info(f"Sell order {self.active_sell_order_id} cancelled successfully")
                    else:
                        self.logger.warning(f"Failed to cancel sell order {self.active_sell_order_id}: {result}")
                except Exception as e:
                    self.logger.error(f"Error cancelling sell order {self.active_sell_order_id}: {str(e)}")
                finally:
                    # Clear order tracking
                    self.active_sell_order_id = None
                    self.active_sell_order_time = None
                    self.active_sell_order_price = None
                    need_cancel_sell = True
        
        return need_cancel_buy, need_cancel_sell
    
    def _auto_cancel_routine(self):
        """Background routine for auto-cancellation checks"""
        while not self.auto_cancel_stop_event.is_set():
            try:
                current_time = time.time()
                
                # SIMPLE SAFETY 1: Run cancel_all every 2 minutes, no conditions
                if current_time - self.last_cancel_all_time > 120:  # 120 seconds = 2 minutes
                    self.logger.info("Running scheduled cancel_all (2-minute interval)")
                    self.order_handler.cancel_all_orders(self.symbol)
                    self.last_cancel_all_time = current_time
                
                # SIMPLE SAFETY 2: Check for tokens after 5 minutes, if any, sell them
                if not self.emergency_sell_done and current_time - self.strategy_start_time > 300:  # 5 minutes
                    asset_balance, _ = self.get_balances()
                    if asset_balance > 0.00001:  # We still have tokens
                        self.logger.warning(f"Found {asset_balance} {self.asset} after 5 minutes, emergency market sell")
                        # Cancel any orders first
                        self.order_handler.cancel_all_orders(self.symbol)
                        # Sell everything at market
                        if self.is_perp:
                            self.order_handler.perp_market_sell(self.symbol, asset_balance, 1, 0.01)
                        else:
                            self.order_handler.market_sell(self.symbol, asset_balance, 0.01)
                    self.emergency_sell_done = True
                
                # Sleep for a short time to avoid excessive CPU usage
                time.sleep(1)
                
            except Exception as e:
                self.logger.error(f"Error in auto-cancel routine: {str(e)}")
                time.sleep(5)  # Sleep longer on error
    
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
        self.strategy_start_time = time.time()
        
        # Start auto-cancellation thread
        self.auto_cancel_running = True
        self.auto_cancel_stop_event.clear()
        self.auto_cancel_thread = threading.Thread(target=self._auto_cancel_routine)
        self.auto_cancel_thread.daemon = True
        self.auto_cancel_thread.start()
        
        # Main strategy loop
        try:
            while not self.stop_requested and self.running:
                current_time = time.time()
                
                # If we're in backoff mode, wait before trying again
                if backoff_time > current_time:
                    time.sleep(0.1)
                    continue
                
                # Get market data for cancellation check
                market_data = self.api_connector.get_market_data(self.symbol)
                if "error" in market_data:
                    self.set_status(f"Error getting market data: {market_data['error']}")
                    time.sleep(1)
                    continue
                
                # Use the enhanced cancellation check
                need_cancel_buy, need_cancel_sell = self._check_and_cancel_orders(market_data)
                
                # If any orders were cancelled, update mid price and balances
                if need_cancel_buy or need_cancel_sell:
                    # Update mid price from the market data we already fetched
                    if "mid_price" in market_data:
                        self.mid_price = market_data["mid_price"]
                    elif "best_bid" in market_data and "best_ask" in market_data:
                        best_bid = market_data["best_bid"]
                        best_ask = market_data["best_ask"]
                        self.mid_price = (best_bid + best_ask) / 2
                    
                    # Get latest balances
                    asset_balance, quote_balance = self.get_balances()
                    
                    # Place new orders if needed
                    if need_cancel_buy and quote_balance > 1.0:
                        self._place_buy_order(market_data)
                        
                    if need_cancel_sell and asset_balance > 0.00001:
                        self._place_sell_order(market_data, asset_balance)
                
                # Check if it's time to refresh
                refresh_needed = (current_time - self.last_tick_time) >= self.refresh_time
                should_check_orders = (current_time - last_order_check) >= 1  # Check order status frequently
                
                # Check order status more frequently than placing new orders
                if should_check_orders:
                    buy_active, sell_active = self._check_orders_status()
                    last_order_check = current_time
                
                # Sleep to avoid excessive CPU usage
                time.sleep(0.01)
                
        except Exception as e:
            self.logger.error(f"Error in strategy loop: {str(e)}", exc_info=True)
            self.set_status(f"Error: {str(e)}")
        
        finally:
            # Stop auto-cancellation thread
            self.auto_cancel_running = False
            self.auto_cancel_stop_event.set()
            if self.auto_cancel_thread:
                self.auto_cancel_thread.join(timeout=5)
            
            # Clean up when stopping
            self._cancel_active_orders()
            self.running = False
            self.set_status("Market making strategy stopped")
    
    def _cancel_active_orders(self):
        """Cancel all active orders for this strategy"""
        try:
            # Simple, straightforward cancel_all with no conditions
            self.order_handler.cancel_all_orders(self.symbol)
            self.logger.info(f"Cancelled all orders for {self.symbol}")
            
            # Reset order tracking variables
            self.active_buy_order_id = None
            self.active_buy_order_time = None
            self.active_buy_order_price = None
            self.active_sell_order_id = None
            self.active_sell_order_time = None
            self.active_sell_order_price = None
        except Exception as e:
            self.logger.error(f"Error cancelling orders: {str(e)}")
    
    def _update_dynamic_spreads(self, market_data):
        """Update spreads based on current market conditions"""
        current_time = time.time()
        
        # Extract market data
        mid_price = market_data.get("mid_price", 0)
        if not mid_price and "best_bid" in market_data and "best_ask" in market_data:
            mid_price = (market_data["best_bid"] + market_data["best_ask"]) / 2
            
        # Get order book data if available
        bid_size = ask_size = volume = None
        if "order_book" in market_data:
            ob = market_data["order_book"]
            # Extract top-level bid/ask sizes
            if "levels" in ob and len(ob["levels"]) >= 2:
                if ob["levels"][0]:  # bids
                    bid_size = sum(float(level.get("sz", 0)) for level in ob["levels"][0][:5])
                if ob["levels"][1]:  # asks  
                    ask_size = sum(float(level.get("sz", 0)) for level in ob["levels"][1][:5])
        
        # Update spread manager
        self.spread_manager.update_market_data(
            mid_price=mid_price,
            bid_price=market_data.get("best_bid"),
            ask_price=market_data.get("best_ask"),
            volume=volume,
            bid_size=bid_size,
            ask_size=ask_size
        )
        
        # Get new dynamic spreads
        new_bid_spread, new_ask_spread = self.spread_manager.get_dynamic_spreads(
            current_spread_bid=self.bid_spread,
            current_spread_ask=self.ask_spread
        )
        
        # Update strategy spreads
        old_bid_spread = self.bid_spread
        old_ask_spread = self.ask_spread
        
        self.bid_spread = new_bid_spread
        self.ask_spread = new_ask_spread
        self.last_spread_update = current_time
        
        # Log significant changes
        if abs(new_bid_spread - old_bid_spread) / old_bid_spread > 0.2:
            self.logger.info(f"Bid spread adjusted: {old_bid_spread:.6f} -> {new_bid_spread:.6f}")
        if abs(new_ask_spread - old_ask_spread) / old_ask_spread > 0.2:
            self.logger.info(f"Ask spread adjusted: {old_ask_spread:.6f} -> {new_ask_spread:.6f}")
    
    def get_performance_metrics(self):
        """Get current performance metrics"""
        try:
            metrics = {
                "symbol": self.symbol,
                "status": self.status_message,
                "mid_price": f"{self.mid_price:.8f}",
                "bid_spread": f"{self.bid_spread:.6f}",
                "ask_spread": f"{self.ask_spread:.6f}",
                "error_count": self.error_count,
                "consecutive_errors": self.consecutive_errors,
                "last_successful_placement": f"{(time.time() - self.last_successful_placement):.1f}s ago" if self.last_successful_placement else "Never"
            }
            
            # Add volatility diagnostics
            vol_diagnostics = self.spread_manager.get_diagnostics()
            metrics.update({
                "dynamic_spreads": "Enabled",
                "original_bid_spread": f"{self.original_bid_spread:.6f}",
                "original_ask_spread": f"{self.original_ask_spread:.6f}",
                "current_bid_spread": f"{self.bid_spread:.6f}",
                "current_ask_spread": f"{self.ask_spread:.6f}",
                "volatility": vol_diagnostics.get("current_volatility", "N/A"),
                "volatility_percentile": vol_diagnostics.get("volatility_percentile", "N/A"),
                "vol_multiplier": vol_diagnostics.get("volatility_multiplier", "N/A"),
                "order_book_imbalance": f"{vol_diagnostics.get('imbalance_bid_adjustment', 1.0):.2f}/{vol_diagnostics.get('imbalance_ask_adjustment', 1.0):.2f}"
            })
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"Error calculating metrics: {str(e)}")
            return {
                "symbol": self.symbol,
                "error": str(e)
            } 