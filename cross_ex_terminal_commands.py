import logging
from prettytable import PrettyTable

class CrossExchangeCommands:
    """Cross-exchange commands to be added to ElysiumTerminalUI"""
    
    def do_connect_bybit(self, arg):
        """
        Connect to Bybit exchange
        Usage: connect_bybit [testnet]
        Options:
            testnet    Connect to testnet (default is mainnet)
        """
        try:
            # Parse network type from arguments
            arg_lower = arg.lower()
            if "testnet" in arg_lower:
                use_testnet = True
                network_name = "testnet"
            else:
                # Default to mainnet
                use_testnet = False
                network_name = "mainnet"
            
            # Import credentials from dontshareconfig.py
            try:
                import dontshareconfig as ds
                
                # Select the appropriate credentials based on network
                if use_testnet:
                    api_key = ds.bybit_testnet_api_key
                    api_secret = ds.bybit_testnet_api_secret
                else:
                    api_key = ds.bybit_mainnet_api_key
                    api_secret = ds.bybit_mainnet_api_secret
            except (ImportError, AttributeError):
                print("Bybit credentials not found in dontshareconfig.py")
                print("Please add the following to dontshareconfig.py:")
                print("bybit_testnet_api_key = 'your_testnet_api_key'")
                print("bybit_testnet_api_secret = 'your_testnet_api_secret'")
                print("bybit_mainnet_api_key = 'your_mainnet_api_key'")
                print("bybit_mainnet_api_secret = 'your_mainnet_api_secret'")
                return
            
            print(f"\nConnecting to Bybit ({network_name})...")
            
            # Initialize Bybit connector if not already initialized
            if not hasattr(self, 'bybit_connector'):
                from bybit_connector import BybitConnector
                self.bybit_connector = BybitConnector(api_key, api_secret, use_testnet)
            else:
                # Update credentials if connector already exists
                self.bybit_connector.api_key = api_key
                self.bybit_connector.api_secret = api_secret
                self.bybit_connector.testnet = use_testnet
            
            # Connect to Bybit
            success = self.bybit_connector.connect()
            
            if success:
                print(f"Successfully connected to Bybit")
                
                # Initialize order handler if not already initialized
                if not hasattr(self, 'bybit_order_handler'):
                    from bybit_order_handler import BybitOrderHandler
                    self.bybit_order_handler = BybitOrderHandler(self.bybit_connector)
                
                # Initialize WebSocket handler if not already initialized
                if not hasattr(self, 'bybit_ws_handler'):
                    from bybit_websocket_handler import BybitWebSocketHandler
                    self.bybit_ws_handler = BybitWebSocketHandler(api_key, api_secret, use_testnet)
                    self.bybit_ws_handler.connect()
            else:
                print("Failed to connect to Bybit")
                    
        except Exception as e:
            print(f"Error connecting to Bybit: {str(e)}")
            
    def do_bybit_balance(self, arg):
        """
        Show current balance on Bybit
        Usage: bybit_balance
        """
        if not hasattr(self, 'bybit_connector') or not self.bybit_connector:
            print("Not connected to Bybit. Use 'connect_bybit' first.")
            return
            
        try:
            print("\n=== Bybit Balances ===")
            
            # Get balances
            balances = self.bybit_connector.get_balances()
            
            headers = ["Asset", "Available", "Total", "In Orders"]
            rows = []
            
            for balance in balances.get("spot", []):
                rows.append([
                    balance.get("asset", ""),
                    float(balance.get("available", 0)),
                    float(balance.get("total", 0)),
                    float(balance.get("in_orders", 0))
                ])
            
            self._print_table(headers, rows)
            
        except Exception as e:
            print(f"\nError fetching Bybit balances: {str(e)}")
            
    def do_bybit_market(self, arg):
        """
        Get current market data from Bybit
        Usage: bybit_market <symbol>
        Example: bybit_market BTCUSDT
        """
        if not hasattr(self, 'bybit_connector') or not self.bybit_connector:
            print("Not connected to Bybit. Use 'connect_bybit' first.")
            return
            
        try:
            args = arg.split()
            if len(args) < 1:
                print("Invalid arguments. Usage: bybit_market <symbol>")
                return
                
            symbol = args[0]
            
            print(f"\nGetting market data for {symbol} on Bybit...")
            
            # Get market data
            market_data = self.bybit_connector.get_market_data(symbol)
            
            if "error" in market_data:
                print(f"Error: {market_data['error']}")
                return
                
            # Extract and display data
            best_bid = market_data.get("best_bid", 0)
            best_ask = market_data.get("best_ask", 0)
            mid_price = market_data.get("mid_price", 0)
            
            print(f"Best bid: {best_bid}")
            print(f"Best ask: {best_ask}")
            print(f"Mid price: {mid_price}")
            print(f"Spread: {best_ask - best_bid} ({(best_ask - best_bid) / best_bid * 100:.4f}%)")
            
            # Display orderbook
            if "order_book" in market_data:
                orderbook = market_data["order_book"]
                
                print("\nBids:")
                for i, bid in enumerate(orderbook.get("b", [])[:5]):
                    print(f"{i+1}. Price: {bid[0]}, Size: {bid[1]}")
                
                print("\nAsks:")
                for i, ask in enumerate(orderbook.get("a", [])[:5]):
                    print(f"{i+1}. Price: {ask[0]}, Size: {ask[1]}")
            
        except Exception as e:
            print(f"\nError getting Bybit market data: {str(e)}")
            
    def do_cross_market(self, arg):
        """
        Show market data comparison between Hyperliquid and Bybit
        Usage: cross_market <hl_symbol> <bybit_symbol>
        Example: cross_market UBTC/USDC BTCUSDT
        """
        if (not hasattr(self, 'api_connector') or not self.api_connector.exchange or
                not hasattr(self, 'bybit_connector') or not self.bybit_connector):
            print("Not connected to both exchanges. Use 'connect' and 'connect_bybit' first.")
            return
            
        try:
            args = arg.split()
            if len(args) < 2:
                print("Invalid arguments. Usage: cross_market <hl_symbol> <bybit_symbol>")
                return
                
            hl_symbol = args[0]
            bybit_symbol = args[1]
            
            print(f"\nComparing market data for {hl_symbol} (HL) and {bybit_symbol} (Bybit)...")
            
            # Get market data from both exchanges
            hl_data = self.api_connector.get_market_data(hl_symbol)
            bybit_data = self.bybit_connector.get_market_data(bybit_symbol)
            
            if "error" in hl_data:
                print(f"Error getting Hyperliquid data: {hl_data['error']}")
                return
                
            if "error" in bybit_data:
                print(f"Error getting Bybit data: {bybit_data['error']}")
                return
                
            # Extract prices
            hl_bid = hl_data.get("best_bid", 0)
            hl_ask = hl_data.get("best_ask", 0)
            hl_mid = hl_data.get("mid_price", 0)
            
            bybit_bid = bybit_data.get("best_bid", 0)
            bybit_ask = bybit_data.get("best_ask", 0)
            bybit_mid = bybit_data.get("mid_price", 0)
            
            # Calculate deltas
            bid_delta = hl_bid - bybit_bid
            bid_delta_pct = (bid_delta / bybit_bid * 100) if bybit_bid else 0
            
            ask_delta = hl_ask - bybit_ask
            ask_delta_pct = (ask_delta / bybit_ask * 100) if bybit_ask else 0
            
            mid_delta = hl_mid - bybit_mid
            mid_delta_pct = (mid_delta / bybit_mid * 100) if bybit_mid else 0
            
            # Display comparison
            table = PrettyTable()
            table.field_names = ["Metric", "Hyperliquid", "Bybit", "Delta", "Delta %"]
            
            table.add_row(["Bid", f"{hl_bid:.8f}", f"{bybit_bid:.8f}", f"{bid_delta:.8f}", f"{bid_delta_pct:.4f}%"])
            table.add_row(["Ask", f"{hl_ask:.8f}", f"{bybit_ask:.8f}", f"{ask_delta:.8f}", f"{ask_delta_pct:.4f}%"])
            table.add_row(["Mid", f"{hl_mid:.8f}", f"{bybit_mid:.8f}", f"{mid_delta:.8f}", f"{mid_delta_pct:.4f}%"])
            
            print(table)
            
            # Check for arbitrage opportunity
            min_arb_threshold = 0.1  # 0.1% minimum threshold
            
            # Scenario 1: Buy on Bybit, Sell on HL
            delta_1 = hl_bid - bybit_ask
            delta_1_pct = (delta_1 / bybit_ask * 100) if bybit_ask else 0
            
            # Scenario 2: Buy on HL, Sell on Bybit
            delta_2 = bybit_bid - hl_ask
            delta_2_pct = (delta_2 / hl_ask * 100) if hl_ask else 0
            
            if delta_1_pct > min_arb_threshold:
                print(f"\nArbitrage opportunity: Buy on Bybit @ {bybit_ask}, Sell on Hyperliquid @ {hl_bid}")
                print(f"Delta: {delta_1:.8f} ({delta_1_pct:.4f}%)")
            elif delta_2_pct > min_arb_threshold:
                print(f"\nArbitrage opportunity: Buy on Hyperliquid @ {hl_ask}, Sell on Bybit @ {bybit_bid}")
                print(f"Delta: {delta_2:.8f} ({delta_2_pct:.4f}%)")
            else:
                print("\nNo significant arbitrage opportunity detected.")
            
        except Exception as e:
            print(f"\nError comparing market data: {str(e)}")
            
    def do_start_arbitrage(self, arg):
        """
        Start cross-exchange arbitrage strategy
        Usage: start_arbitrage <symbol> [mode]
        Example: start_arbitrage UBTC/USDC live
        Options:
            symbol    Base symbol (e.g., UBTC/USDC)
            mode      'live' or 'simulation' (default is simulation)
        """
        if (not hasattr(self, 'api_connector') or not self.api_connector.exchange or
                not hasattr(self, 'bybit_connector') or not self.bybit_connector):
            print("Not connected to both exchanges. Use 'connect' and 'connect_bybit' first.")
            return
            
        try:
            args = arg.split()
            if len(args) < 1:
                print("Invalid arguments. Usage: start_arbitrage <symbol> [mode]")
                return
                
            symbol = args[0]
            mode = args[1].lower() if len(args) > 1 else "simulation"
            
            if mode not in ["live", "simulation"]:
                print("Invalid mode. Use 'live' or 'simulation'.")
                return
                
            print(f"\nStarting cross-exchange arbitrage for {symbol} in {mode} mode...")
            
            # Initialize required components if not already initialized
            if not hasattr(self, 'exchange_config'):
                from exchange_config import ExchangeConfig
                self.exchange_config = ExchangeConfig()
                
            if not hasattr(self, 'exchange_manager'):
                from exchange_manager import ExchangeManager
                self.exchange_manager = ExchangeManager(self.exchange_config)
                
                # Add exchanges to manager
                self.exchange_manager.add_exchange("hyperliquid", self.api_connector, self.order_handler)
                self.exchange_manager.add_exchange("bybit", self.bybit_connector, self.bybit_order_handler)
                
                # Connect exchanges
                self.exchange_manager.connect_all()
                
            if not hasattr(self, 'market_data_normalizer'):
                from market_data_normalizer import MarketDataNormalizer
                self.market_data_normalizer = MarketDataNormalizer()
                
            if not hasattr(self, 'inventory_tracker'):
                from inventory_tracker import InventoryTracker
                self.inventory_tracker = InventoryTracker(self.exchange_config)
                
                # Initialize with current balances
                for exchange_id in ["hyperliquid", "bybit"]:
                    balances = self.exchange_manager.get_balances(exchange_id)
                    self.inventory_tracker.update_balances(exchange_id, balances)
                
            if not hasattr(self, 'delta_engine'):
                from delta_engine import DeltaEngine
                self.delta_engine = DeltaEngine(self.exchange_config)
                
            # Configure strategy parameters
            strategy_params = {
                "symbol": {"value": symbol},
                "execution_mode": {"value": mode},
                "min_delta_percentage": {"value": 0.1},  # 0.1% minimum threshold
                "max_order_size": {"value": 0.01},       # 0.01 BTC/ETH/etc.
                "refresh_time": {"value": 1}             # 1 second refresh
            }
            
            # Initialize and start arbitrage strategy
            from arbitrage_strategy import ArbitrageStrategy
            
            if hasattr(self, 'arbitrage_strategy'):
                # Stop existing strategy if running
                if self.arbitrage_strategy.is_running():
                    self.arbitrage_strategy.stop()
                    print("Stopped existing arbitrage strategy.")
            
            # Create new strategy instance
            self.arbitrage_strategy = ArbitrageStrategy(
                self.api_connector,
                self.order_handler,
                self.config_manager,
                self.exchange_manager,
                self.delta_engine,
                self.inventory_tracker,
                self.market_data_normalizer,
                strategy_params
            )
            
            # Start the strategy
            import threading
            
            # Start in a new thread
            threading.Thread(target=self.arbitrage_strategy.start, daemon=True).start()
            
            print(f"Cross-exchange arbitrage strategy started for {symbol} in {mode} mode.")
            print("Use 'arb_status' to check status and 'stop_arbitrage' to stop.")
            
        except Exception as e:
            print(f"\nError starting arbitrage strategy: {str(e)}")
            
    def do_stop_arbitrage(self, arg):
        """
        Stop cross-exchange arbitrage strategy
        Usage: stop_arbitrage
        """
        if not hasattr(self, 'arbitrage_strategy'):
            print("No arbitrage strategy is running.")
            return
            
        try:
            if self.arbitrage_strategy.is_running():
                self.arbitrage_strategy.stop()
                print("Arbitrage strategy stopped.")
            else:
                print("Arbitrage strategy is not running.")
                
        except Exception as e:
            print(f"\nError stopping arbitrage strategy: {str(e)}")
            
    def do_arb_status(self, arg):
        """
        Check status of cross-exchange arbitrage strategy
        Usage: arb_status
        """
        if not hasattr(self, 'arbitrage_strategy'):
            print("No arbitrage strategy is initialized.")
            return
            
        try:
            status = self.arbitrage_strategy.get_status()
            running = self.arbitrage_strategy.is_running()
            
            print("\n=== Arbitrage Strategy Status ===")
            print(f"Running: {'Yes' if running else 'No'}")
            print(f"Status: {status}")
            
            # Get performance metrics
            metrics = self.arbitrage_strategy.get_performance_metrics()
            
            if metrics:
                print("\nPerformance Metrics:")
                for key, value in metrics.items():
                    print(f"  {key}: {value}")
                    
        except Exception as e:
            print(f"\nError checking arbitrage status: {str(e)}")