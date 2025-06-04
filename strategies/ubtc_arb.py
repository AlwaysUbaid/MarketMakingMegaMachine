import time
from .strategy_selector import TradingStrategy

class UBTCArbitrageStrategy(TradingStrategy):
    def __init__(self, api_connector, order_handler, symbol="UBTC-PERP", is_perp=True, leverage=1):
        super().__init__(api_connector, order_handler, symbol, is_perp, leverage)
        self.strategy_name = "UBTC Arbitrage"
        self.refresh_time = 1  # Refresh every second
        self.order_max_age = 30  # Cancel orders after 30 seconds
        self.last_cancel_time = time.time()
        self.last_tick_time = time.time()
        self.active_buy_order_id = None
        self.active_sell_order_id = None
        self.active_buy_order_time = None
        self.active_sell_order_time = None
        self.mid_price = None
        self.running = False
        self.stop_requested = False
        self.instance_id = id(self)

    def _run_strategy(self):
        """Main strategy execution loop"""
        self.set_status("Starting arbitrage strategy")
        
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
                    # Before calling cancel_all_orders, log open orders
                    open_orders = self.order_handler.get_open_orders()
                    self.logger.info(f"[Instance {self.instance_id}] Open orders before cancel: {open_orders}")
                    self.order_handler.cancel_all_orders()
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
        except Exception as e:
            self.logger.error(f"Error in strategy execution: {str(e)}")
            self.set_status(f"Error: {str(e)}")
            self.running = False 