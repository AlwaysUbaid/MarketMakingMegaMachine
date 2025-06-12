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
    
    This strategy rapidly executes market orders for the USDHL/USDC pair,
    focusing on volume rather than spread since it's a stablecoin pair.
    """
    
    # Strategy metadata
    STRATEGY_NAME = "USDHL Market Making"
    STRATEGY_DESCRIPTION = "Rapid market order execution for stablecoin pair"
    
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
        "slippage": {
            "value": 0.0001,  # 0.01% slippage tolerance
            "type": "float",
            "description": "Maximum allowed slippage for market orders"
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
        self.slippage = self._get_param_value("slippage")
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
        
        # Extract asset name from symbol for balance lookup
        self.asset = self.symbol.split('/')[0] if '/' in self.symbol else self.symbol
        
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
    
    def _execute_market_trade(self, is_buy: bool) -> bool:
        """
        Execute a market trade
        
        Args:
            is_buy: True for buy, False for sell
            
        Returns:
            bool: True if trade was successful
        """
        try:
            if is_buy:
                if self.is_perp:
                    result = self.order_handler.perp_market_buy(self.symbol, self.order_amount, self.leverage, self.slippage)
                else:
                    result = self.order_handler.market_buy(self.symbol, self.order_amount, self.slippage)
            else:
                if self.is_perp:
                    result = self.order_handler.perp_market_sell(self.symbol, self.order_amount, self.leverage, self.slippage)
                else:
                    result = self.order_handler.market_sell(self.symbol, self.order_amount, self.slippage)
            
            if result and result.get("status") == "ok":
                self.logger.info(f"Successfully executed {'buy' if is_buy else 'sell'} market order")
                self.last_successful_trade = time.time()
                return True
            else:
                error_msg = result.get("message", "Unknown error") if result else "No result"
                self.logger.error(f"Failed to execute {'buy' if is_buy else 'sell'} market order: {error_msg}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error executing market trade: {str(e)}")
            return False
    
    def _get_size_decimals(self):
        """Get the allowed number of decimals for the symbol from exchange metadata, fallback to 8."""
        try:
            if self.api_connector and self.api_connector.info:
                meta = self.api_connector.info.meta()
                for asset_info in meta.get("universe", []):
                    if asset_info.get("name") == self.symbol:
                        return asset_info.get("szDecimals", 8)
        except Exception as e:
            self.logger.warning(f"Could not fetch size decimals from metadata: {e}")
        return 8

    def _format_size(self, size):
        """Format the order size to the allowed number of decimals."""
        decimals = self._get_size_decimals()
        return round(size, decimals)

    def _run_strategy(self):
        """Main strategy execution loop"""
        self.set_status("Starting stablecoin market making strategy")
        
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
        last_trade_side = False  # False means last was sell, so we should buy next
        
        # Format order amount
        formatted_order_amount = self._format_size(self.order_amount)
        self.logger.info(f"Using formatted order amount: {formatted_order_amount}")
        
        # Main strategy loop
        try:
            while not self.stop_requested and self.running:
                current_time = time.time()
                
                # If we're in backoff mode, wait before trying again
                if backoff_time > current_time:
                    time.sleep(0.1)
                    continue
                
                # Check if it's time to trade
                if (current_time - self.last_tick_time) >= self.refresh_time:
                    # Get latest balances
                    asset_balance, quote_balance = self.get_balances()
                    
                    # Initialize success variable
                    success = False
                    
                    # Execute trade based on last trade side
                    if not last_trade_side:  # Last was sell, now buy
                        if quote_balance >= formatted_order_amount:
                            success = self._execute_market_trade(True)  # Buy
                            if success:
                                last_trade_side = True
                        else:
                            self.logger.warning(f"Insufficient {self.quote_asset} balance for buy: {quote_balance} < {formatted_order_amount}")
                    else:  # Last was buy, now sell
                        # Format the available balance
                        available_balance = self._format_size(asset_balance)
                        if available_balance >= formatted_order_amount:
                            success = self._execute_market_trade(False)  # Sell
                            if success:
                                last_trade_side = False
                        else:
                            self.logger.warning(f"Insufficient {self.asset} balance for sell: {available_balance} < {formatted_order_amount}")
                    
                    # Update tracking variables
                    if success:
                        self.set_status(f"Successfully executed {'buy' if not last_trade_side else 'sell'} trade")
                        self.last_tick_time = current_time
                        self.consecutive_errors = 0
                    else:
                        self.consecutive_errors += 1
                        self.error_count += 1
                        
                        # Implement backoff if we keep failing
                        if self.consecutive_errors > 3:
                            backoff_seconds = min(30, 2 ** (self.consecutive_errors - 3))
                            backoff_time = current_time + backoff_seconds
                            self.set_status(f"Trade execution issues, backing off for {backoff_seconds}s")
                
                # Sleep to avoid excessive CPU usage
                time.sleep(0.01)
                
        except Exception as e:
            self.logger.error(f"Error in strategy loop: {str(e)}", exc_info=True)
            self.set_status(f"Error: {str(e)}")
        
        finally:
            self.running = False
            self.set_status("Market making strategy stopped")
    
    def get_performance_metrics(self):
        """
        Get performance metrics for the strategy
        
        Returns:
            dict: Performance metrics
        """
        try:
            asset_balance, quote_balance = self.get_balances()

            metrics = {
                "symbol": self.symbol,
                "asset_balance": asset_balance,
                "quote_balance": quote_balance,
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
        self.set_status("Instance cleaned up") 