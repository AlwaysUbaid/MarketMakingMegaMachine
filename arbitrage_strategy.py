import logging
import threading
import time
from datetime import datetime

# Import base class
from strategy_selector import TradingStrategy

class ArbitrageStrategy(TradingStrategy):
    """
    Cross-Exchange Arbitrage Strategy
    
    This strategy detects and executes on price differences between
    Hyperliquid and Bybit exchanges.
    """
    
    # Strategy metadata
    STRATEGY_NAME = "Cross-Exchange Arbitrage"
    STRATEGY_DESCRIPTION = "Executes trades based on price differences between exchanges"
    
    # Default parameters with descriptions
    STRATEGY_PARAMS = {
        "symbol": {
            "value": "UBTC/USDC",
            "type": "str",
            "description": "Base trading pair symbol"
        },
        "min_delta_percentage": {
            "value": 0.1,  # 0.1%
            "type": "float",
            "description": "Minimum price difference percentage to trigger arbitrage"
        },
        "max_order_size": {
            "value": 0.01,
            "type": "float",
            "description": "Maximum order size for each arbitrage trade"
        },
        "max_inventory_imbalance": {
            "value": 0.03,
            "type": "float",
            "description": "Maximum allowed inventory imbalance between exchanges"
        },
        "refresh_time": {
            "value": 1,  # 1 second
            "type": "int",
            "description": "Time in seconds between arbitrage checks"
        },
        "execution_mode": {
            "value": "live",  # "live" or "simulation"
            "type": "str",
            "description": "Strategy execution mode"
        },
        "enabled_exchanges": {
            "value": ["hyperliquid", "bybit"],
            "type": "list",
            "description": "Exchanges to include in arbitrage"
        }
    }
    
    def __init__(self, api_connector, order_handler, config_manager, exchange_manager, 
                delta_engine, inventory_tracker, market_data_normalizer, params=None):
        """Initialize the arbitrage strategy with dependencies"""
        super().__init__(api_connector, order_handler, config_manager, params)
        
        # Store dependencies
        self.exchange_manager = exchange_manager
        self.delta_engine = delta_engine
        self.inventory_tracker = inventory_tracker
        self.normalizer = market_data_normalizer
        
        # Extract parameter values
        self.symbol = self._get_param_value("symbol")
        self.min_delta_percentage = self._get_param_value("min_delta_percentage")
        self.max_order_size = self._get_param_value("max_order_size")
        self.max_inventory_imbalance = self._get_param_value("max_inventory_imbalance")
        self.refresh_time = self._get_param_value("refresh_time")
        self.execution_mode = self._get_param_value("execution_mode")
        self.enabled_exchanges = self._get_param_value("enabled_exchanges")
        
        # Runtime variables
        self.last_check_time = 0
        self.status_message = "Initialized"
        self.status_lock = threading.Lock()
        self.active_trades = []
        self.trade_history = []
        self.error_count = 0
        self.consecutive_errors = 0
        self.profitable_trades = 0
        self.unprofitable_trades = 0
        self.total_profit = 0
        
        # Symbol mappings
        self.symbol_mappings = {}
        for exchange in self.enabled_exchanges:
            if exchange == "hyperliquid":
                self.symbol_mappings[exchange] = self.symbol  # Same format
            elif exchange == "bybit":
                # Convert from UBTC/USDC to BTCUSDT format
                if self.symbol == "UBTC/USDC":
                    self.symbol_mappings[exchange] = "BTCUSDT"
                elif self.symbol == "UETH/USDC":
                    self.symbol_mappings[exchange] = "ETHUSDT"
                elif self.symbol == "USOL/USDC":
                    self.symbol_mappings[exchange] = "SOLUSDT"
                else:
                    # Default mapping (may need adjusting)
                    base = self.symbol.split('/')[0].replace('U', '')
                    quote = self.symbol.split('/')[1]
                    if quote == "USDC":
                        quote = "USDT"  # Bybit typically uses USDT
                    self.symbol_mappings[exchange] = f"{base}{quote}"
        
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
    
    def _run_strategy(self):
        """Main strategy execution loop"""
        self.set_status("Starting cross-exchange arbitrage strategy")
        
        # Verify exchange connections
        for exchange in self.enabled_exchanges:
            if not self.exchange_manager.is_connected(exchange):
                self.set_status(f"Error: Exchange {exchange} is not connected. Please connect first.")
                self.logger.error(f"Exchange {exchange} not connected when starting strategy")
                self.running = False
                return
        
        # Initial check of balances
        self._update_balances()
        
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
                
                # Check if it's time to refresh
                refresh_needed = (current_time - self.last_check_time) >= self.refresh_time
                
                if refresh_needed:
                    try:
                        # 1. Update market data
                        self._update_market_data()
                        
                        # 2. Find arbitrage opportunities
                        signals = self.delta_engine.find_arbitrage_opportunities()
                        
                        # 3. Execute on signals if found
                        if signals:
                            for signal in signals:
                                self._execute_arbitrage(signal)
                        
                        # 4. Update balances periodically
                        if (current_time - self.last_check_time) >= 10:  # Every 10 seconds
                            self._update_balances()
                        
                        # Update tracking variables
                        self.last_check_time = current_time
                        self.consecutive_errors = 0
                        
                    except Exception as e:
                        self.consecutive_errors += 1
                        self.error_count += 1
                        self.logger.error(f"Error in arbitrage loop: {str(e)}")
                        
                        # Implement backoff if we keep failing
                        if self.consecutive_errors > 3:
                            backoff_seconds = min(30, 2 ** (self.consecutive_errors - 3))
                            backoff_time = current_time + backoff_seconds
                            self.set_status(f"Strategy errors, backing off for {backoff_seconds}s")
                
                # Sleep to avoid excessive CPU usage
                time.sleep(0.01)
                
        except Exception as e:
            self.logger.error(f"Critical error in strategy loop: {str(e)}", exc_info=True)
            self.set_status(f"Error: {str(e)}")
        
        finally:
            # Clean up when stopping
            self._cleanup()
            self.running = False
            self.set_status("Cross-exchange arbitrage strategy stopped")
    
    def _update_market_data(self):
        """Update market data for all exchanges and symbols"""
        for exchange in self.enabled_exchanges:
            symbol = self.symbol_mappings.get(exchange)
            if not symbol:
                continue
                
            # Get market data
            market_data = self.exchange_manager.get_market_data(exchange, symbol)
            
            if "error" in market_data:
                self.logger.error(f"Error getting market data for {exchange} {symbol}: {market_data['error']}")
                continue
            
            # Normalize data
            normalized_data = self.normalizer.normalize_orderbook(exchange, self.symbol, market_data)
            
            # Update delta engine
            if normalized_data:
                self.delta_engine.update_market_data(exchange, self.symbol, normalized_data)
    
    def _update_balances(self):
       """Update balances for all exchanges"""
       for exchange in self.enabled_exchanges:
           # Get balances
           balances = self.exchange_manager.get_balances(exchange)
           
           # Update inventory tracker
           self.inventory_tracker.update_balances(exchange, balances)
           
           # Log balances
           if exchange == "hyperliquid":
               # Extract asset and quote asset
               asset = self.symbol.split('/')[0] if '/' in self.symbol else self.symbol
               quote_asset = self.symbol.split('/')[1] if '/' in self.symbol else "USDC"
               
               asset_balance = 0
               quote_balance = 0
               
               # Get asset balance
               if asset in self.inventory_tracker.balances[exchange]:
                   asset_balance = self.inventory_tracker.balances[exchange][asset].get("total", 0)
               
               # Get quote balance
               if quote_asset in self.inventory_tracker.balances[exchange]:
                   quote_balance = self.inventory_tracker.balances[exchange][quote_asset].get("total", 0)
                   
               self.logger.info(f"Hyperliquid balances: {asset_balance} {asset}, {quote_balance} {quote_asset}")
           
           elif exchange == "bybit":
               # For Bybit, we need to map the assets differently
               asset = self.symbol.split('/')[0].replace('U', '') if '/' in self.symbol else self.symbol.replace('U', '')
               quote_asset = "USDT"  # Typically USDT for Bybit
               
               asset_balance = 0
               quote_balance = 0
               
               # Get asset balance
               if asset in self.inventory_tracker.balances[exchange]:
                   asset_balance = self.inventory_tracker.balances[exchange][asset].get("total", 0)
               
               # Get quote balance
               if quote_asset in self.inventory_tracker.balances[exchange]:
                   quote_balance = self.inventory_tracker.balances[exchange][quote_asset].get("total", 0)
                   
               self.logger.info(f"Bybit balances: {asset_balance} {asset}, {quote_balance} {quote_asset}")
   
    def _execute_arbitrage(self, signal):
        """
        Execute arbitrage based on a signal
        
        Args:
            signal: Arbitrage signal with details
        """
        if not signal:
            return
            
        # Extract signal details
        symbol = signal["symbol"]
        buy_exchange = signal["buy_exchange"]
        sell_exchange = signal["sell_exchange"]
        buy_price = signal["buy_price"]
        sell_price = signal["sell_price"]
        delta_percentage = signal["delta_percentage"]
        proposed_order_size = signal["order_size"]
        
        # Get mapped symbols for each exchange
        buy_symbol = self.symbol_mappings.get(buy_exchange)
        sell_symbol = self.symbol_mappings.get(sell_exchange)
        
        if not buy_symbol or not sell_symbol:
            self.logger.error(f"Symbol mapping not found for {buy_exchange} or {sell_exchange}")
            return
            
        # Check if execution should be simulated or live
        if self.execution_mode == "simulation":
            self.logger.info(f"[SIMULATION] Arbitrage opportunity: Buy {proposed_order_size} {buy_symbol} on {buy_exchange} @ {buy_price}, "
                                f"Sell on {sell_exchange} @ {sell_price}, Delta: {delta_percentage:.2f}%")
            return
        
        # 1. Check balance availability
        # For buy side, we need quote currency
        # For sell side, we need base currency
        # Get assets
        base_asset = symbol.split('/')[0] if '/' in symbol else symbol
        quote_asset = symbol.split('/')[1] if '/' in symbol else "USDC"
        
        # Adjust assets based on exchange
        buy_quote_asset = "USDT" if buy_exchange == "bybit" else quote_asset
        buy_base_asset = base_asset.replace('U', '') if buy_exchange == "bybit" else base_asset
        
        sell_quote_asset = "USDT" if sell_exchange == "bybit" else quote_asset
        sell_base_asset = base_asset.replace('U', '') if sell_exchange == "bybit" else base_asset
        
        # Calculate required balances
        buy_quote_required = proposed_order_size * buy_price * 1.01  # Add 1% buffer for fees/slippage
        sell_base_required = proposed_order_size
        
        # Check if sufficient balances are available
        buy_sufficient = self.inventory_tracker.check_sufficient_balance(buy_exchange, buy_quote_asset, buy_quote_required)
        sell_sufficient = self.inventory_tracker.check_sufficient_balance(sell_exchange, sell_base_asset, sell_base_required)
        
        if not buy_sufficient or not sell_sufficient:
            self.logger.warning(f"Insufficient balance for arbitrage: "
                                f"Need {buy_quote_required} {buy_quote_asset} on {buy_exchange} and "
                                f"{sell_base_required} {sell_base_asset} on {sell_exchange}")
            return
        
        # 2. Check for excessive inventory imbalance
        buy_asset_balance = self.inventory_tracker.get_balance(buy_exchange, buy_base_asset)
        sell_asset_balance = self.inventory_tracker.get_balance(sell_exchange, sell_base_asset)
        
        buy_asset_total = buy_asset_balance.get("total", 0) if buy_asset_balance else 0
        sell_asset_total = sell_asset_balance.get("total", 0) if sell_asset_balance else 0
        
        # Calculate imbalance ratio
        if buy_asset_total + sell_asset_total > 0:
            imbalance_ratio = abs(buy_asset_total - sell_asset_total) / (buy_asset_total + sell_asset_total)
            
            if imbalance_ratio > self.max_inventory_imbalance:
                self.logger.warning(f"Excessive inventory imbalance: {imbalance_ratio:.2f} > {self.max_inventory_imbalance}, "
                                    f"{buy_asset_total} on {buy_exchange}, {sell_asset_total} on {sell_exchange}")
                
                # If excessive imbalance, we could either skip this trade or
                # adjust the direction to rebalance inventory
                # Here we're skipping for simplicity
                return
        
        # 3. Place market orders
        trade_id = f"arb_{int(time.time() * 1000)}"
        
        # Record start time for latency tracking
        start_time = time.time()
        
        # Place buy order
        buy_order = {
            "id": f"{trade_id}_buy",
            "exchange": buy_exchange,
            "symbol": buy_symbol,
            "side": "buy",
            "type": "market",
            "size": proposed_order_size,
            "price": buy_price,
            "timestamp": datetime.now().timestamp() * 1000
        }
        
        # Place sell order
        sell_order = {
            "id": f"{trade_id}_sell",
            "exchange": sell_exchange,
            "symbol": sell_symbol,
            "side": "sell",
            "type": "market",
            "size": proposed_order_size,
            "price": sell_price,
            "timestamp": datetime.now().timestamp() * 1000
        }
        
        # Execute orders
        self.logger.info(f"Executing arbitrage: Buy {proposed_order_size} {buy_symbol} on {buy_exchange} @ {buy_price}, "
                            f"Sell on {sell_exchange} @ {sell_price}, Delta: {delta_percentage:.2f}%")
        
        # Add in-flight trades to inventory tracker
        self.inventory_tracker.add_in_flight_trade({
            "id": buy_order["id"],
            "exchange": buy_exchange,
            "asset": buy_base_asset,
            "side": "buy",
            "size": proposed_order_size,
            "price": buy_price
        })
        
        self.inventory_tracker.add_in_flight_trade({
            "id": sell_order["id"],
            "exchange": sell_exchange,
            "asset": sell_base_asset,
            "side": "sell",
            "size": proposed_order_size,
            "price": sell_price
        })
        
        # Execute buy order
        buy_result = self.exchange_manager.place_order(
            buy_exchange, "market", buy_symbol, "buy", proposed_order_size
        )
        
        # Execute sell order
        sell_result = self.exchange_manager.place_order(
            sell_exchange, "market", sell_symbol, "sell", proposed_order_size
        )
        
        # Calculate execution time
        execution_time = time.time() - start_time
        
        # Record trade
        trade_record = {
            "id": trade_id,
            "timestamp": datetime.now().timestamp() * 1000,
            "symbol": symbol,
            "buy_exchange": buy_exchange,
            "sell_exchange": sell_exchange,
            "size": proposed_order_size,
            "buy_price": buy_price,
            "sell_price": sell_price,
            "delta_percentage": delta_percentage,
            "buy_result": buy_result,
            "sell_result": sell_result,
            "execution_time_ms": execution_time * 1000,
            "expected_profit": (sell_price - buy_price) * proposed_order_size
        }
        
        # Analyze results
        buy_success = buy_result.get("status") == "ok"
        sell_success = sell_result.get("status") == "ok"
        
        if buy_success and sell_success:
            self.logger.info(f"Arbitrage executed successfully in {execution_time*1000:.2f}ms, "
                            f"expected profit: {trade_record['expected_profit']:.8f}")
            
            # Update trade stats
            self.profitable_trades += 1
            self.total_profit += trade_record["expected_profit"]
        else:
            self.logger.error(f"Arbitrage execution failed: Buy success: {buy_success}, Sell success: {sell_success}")
            self.unprofitable_trades += 1
        
        # Add to trade history
        self.trade_history.append(trade_record)
        
        # Remove in-flight trades
        self.inventory_tracker.remove_in_flight_trade(buy_order["id"])
        self.inventory_tracker.remove_in_flight_trade(sell_order["id"])
        
        # Update status
        self.set_status(f"Executed arbitrage: {buy_exchange}->{sell_exchange}, {delta_percentage:.2f}%")
    
    def _cleanup(self):
        """Clean up any resources when stopping the strategy"""
        # Nothing special to clean up for this strategy
        pass
    
    def get_performance_metrics(self):
        """
        Get performance metrics for the strategy
        
        Returns:
            dict: Performance metrics
        """
        try:
            # Calculate metrics
            win_rate = (self.profitable_trades / (self.profitable_trades + self.unprofitable_trades) * 100) if (self.profitable_trades + self.unprofitable_trades) > 0 else 0
            
            metrics = {
                "symbol": self.symbol,
                "profitable_trades": self.profitable_trades,
                "unprofitable_trades": self.unprofitable_trades,
                "win_rate": f"{win_rate:.2f}%",
                "total_profit": self.total_profit,
                "errors": self.error_count,
                "active_exchanges": ", ".join(self.enabled_exchanges),
                "execution_mode": self.execution_mode,
                "last_update": datetime.fromtimestamp(self.last_check_time).strftime("%Y-%m-%d %H:%M:%S") if self.last_check_time else "Never"
            }
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"Error calculating metrics: {str(e)}")
            return {
                "symbol": self.symbol,
                "error": str(e)
            }