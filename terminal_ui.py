import cmd
import os
import time
import threading
import logging
import json
import queue
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

class ElysiumTerminalUI(cmd.Cmd):
    """Command-line interface for MMMM Trading Platform"""
    
    VERSION = "2.0.0"
    intro = None

    ASCII_ART = '''
    ███╗   ███╗███╗   ███╗███╗   ███╗███╗   ███╗
    ████╗ ████║████╗ ████║████╗ ████║████╗ ████║
    ██╔████╔██║██╔████╔██║██╔████╔██║██╔████╔██║
    ██║╚██╔╝██║██║╚██╔╝██║██║╚██╔╝██║██║╚██╔╝██║
    ██║ ╚═╝ ██║██║ ╚═╝ ██║██║ ╚═╝ ██║██║ ╚═╝ ██║
    ╚═╝     ╚═╝╚═╝     ╚═╝╚═╝     ╚═╝╚═╝     ╚═╝
    ═══════ Market Making Mega Machine ═══════
    ═══════════════════════════════════════════
    '''

    WELCOME_MSG = '''
    Welcome to MMMM — Market Making Mega Machine
    Type 'help' to see available commands

    Useful Commands:
    - balance     See your exchange balances
    - positions   Show your open positions

    Spot Trading:
    - buy         Execute a market buy
    - sell        Execute a market sell
    - limit_buy   Place a limit buy order
    - limit_sell  Place a limit sell order

    Perpetual Trading:
    - perp_buy        Execute a perpetual market buy
    - perp_sell       Execute a perpetual market sell
    - perp_limit_buy  Place a perpetual limit buy order
    - perp_limit_sell Place a perpetual limit sell order
    - close_position  Close an entire perpetual position
    - set_leverage    Set leverage for a symbol

    Strategy Trading:
    - select_strategy  Select and configure a trading strategy
    - strategy_status  Check the status of the current strategy
    - stop_strategy    Stop the currently running strategy
    - strategy_params  View parameters of a strategy
    - help_strategies  Show help for trading strategies

    Order Management:
    - cancel      Cancel specific order
    - cancel_all  Cancel all open orders
    - orders      List open orders
    - help        List all commands
    '''


    def __init__(self, api_connector, order_handler, config_manager):
        super().__init__()
        self.prompt = '>>> '
        self.api_connector = api_connector
        self.order_handler = order_handler
        self.config_manager = config_manager
        self.authenticated = True  # Set to True by default
        self.last_command_output = ""

        # Initialize strategy selector
        from strategy_selector import StrategySelector
        self.strategy_selector = StrategySelector(api_connector, order_handler, config_manager)
        
    def preloop(self):
        """Setup before starting the command loop"""
        self.display_layout()
        print("Ready to trade!\n")
    
    def display_layout(self):
        """Display the interface layout"""
        os.system('cls' if os.name == 'nt' else 'clear')
        print(self.ASCII_ART)
        print(self.WELCOME_MSG)
        
    def do_connect(self, arg):
        """
        Connect to Hyperliquid exchange
        Usage: connect [mainnet|testnet]
        Options:
            mainnet    Connect to mainnet (default)
            testnet    Connect to testnet
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
            import dontshareconfig as ds
            
            # Select the appropriate credentials based on network
            if use_testnet:
                wallet_address = ds.testnet_wallet
                secret_key = ds.testnet_secret
            else:
                wallet_address = ds.mainnet_wallet
                secret_key = ds.mainnet_secret
            
            print(f"\nConnecting to Hyperliquid ({network_name})...")
            success = self.api_connector.connect_hyperliquid(wallet_address, secret_key, use_testnet)
            
            if success:
                print(f"Successfully connected to {wallet_address}")
                # Initialize order handler with the connected exchange and info objects
                self.order_handler.exchange = self.api_connector.exchange
                self.order_handler.info = self.api_connector.info
                self.order_handler.wallet_address = wallet_address
            else:
                print("Failed to connect to exchange")
                    
        except Exception as e:
            print(f"Error connecting to exchange: {str(e)}")
    
    def do_balance(self, arg):
        """
        Show current balance across spot and perpetual markets
        Usage: balance
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            print("\n=== Current Balances ===")
            
            # Display spot balances
            print("\nSpot Balances:")
            spot_state = self.api_connector.info.spot_user_state(self.api_connector.wallet_address)
            
            headers = ["Asset", "Available", "Total", "In Orders"]
            rows = []
            
            for balance in spot_state.get("balances", []):
                rows.append([
                    balance.get("coin", ""),
                    float(balance.get("available", 0)),
                    float(balance.get("total", 0)),
                    float(balance.get("total", 0)) - float(balance.get("available", 0))
                ])
            
            self._print_table(headers, rows)
            
            # Display perpetual balance
            print("\nPerpetual Account Summary:")
            perp_state = self.api_connector.info.user_state(self.api_connector.wallet_address)
            margin_summary = perp_state.get("marginSummary", {})
            
            headers = ["Metric", "Value"]
            rows = [
                ["Account Value", f"${float(margin_summary.get('accountValue', 0)):.2f}"],
                ["Total Margin Used", f"${float(margin_summary.get('totalMarginUsed', 0)):.2f}"],
                ["Total Position Value", f"${float(margin_summary.get('totalNtlPos', 0)):.2f}"]
            ]
            
            self._print_table(headers, rows)
            
        except Exception as e:
            print(f"\nError fetching balances: {str(e)}")
    
    def do_buy(self, arg):
        """
        Execute a market buy order
        Usage: buy <symbol> <size> [slippage]
        Example: buy ETH 0.1 0.05
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            args = arg.split()
            if len(args) < 2:
                print("Invalid arguments. Usage: buy <symbol> <size> [slippage]")
                return
                
            symbol = args[0]
            size = float(args[1])
            slippage = float(args[2]) if len(args) > 2 else 0.05
            
            print(f"\nExecuting market buy: {size} {symbol} (slippage: {slippage*100}%)")
            result = self.order_handler.market_buy(symbol, size, slippage)
            
            if result["status"] == "ok":
                print("Market buy order executed successfully")
                # Display the details
                if "response" in result and "data" in result["response"] and "statuses" in result["response"]["data"]:
                    for status in result["response"]["data"]["statuses"]:
                        if "filled" in status:
                            filled = status["filled"]
                            print(f"Filled: {filled['totalSz']} @ {filled['avgPx']}")
            else:
                print(f"Market buy order failed: {result.get('message', 'Unknown error')}")
                
        except Exception as e:
            print(f"\nError executing market buy: {str(e)}")
    
    def do_sell(self, arg):
        """
        Execute a market sell order
        Usage: sell <symbol> <size> [slippage]
        Example: sell ETH 0.1 0.05
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            args = arg.split()
            if len(args) < 2:
                print("Invalid arguments. Usage: sell <symbol> <size> [slippage]")
                return
                
            symbol = args[0]
            size = float(args[1])
            slippage = float(args[2]) if len(args) > 2 else 0.05
            
            print(f"\nExecuting market sell: {size} {symbol} (slippage: {slippage*100}%)")
            result = self.order_handler.market_sell(symbol, size, slippage)
            
            if result["status"] == "ok":
                print("Market sell order executed successfully")
                # Display the details
                if "response" in result and "data" in result["response"] and "statuses" in result["response"]["data"]:
                    for status in result["response"]["data"]["statuses"]:
                        if "filled" in status:
                            filled = status["filled"]
                            print(f"Filled: {filled['totalSz']} @ {filled['avgPx']}")
            else:
                print(f"Market sell order failed: {result.get('message', 'Unknown error')}")
                
        except Exception as e:
            print(f"\nError executing market sell: {str(e)}")
    
    def do_limit_buy(self, arg):
        """
        Place a limit buy order
        Usage: limit_buy <symbol> <size> <price>
        Example: limit_buy ETH 0.1 3000
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            args = arg.split()
            if len(args) < 3:
                print("Invalid arguments. Usage: limit_buy <symbol> <size> <price>")
                return
                
            symbol = args[0]
            size = float(args[1])
            price = float(args[2])
            
            print(f"\nPlacing limit buy order: {size} {symbol} @ {price}")
            result = self.order_handler.limit_buy(symbol, size, price)
            
            if result["status"] == "ok":
                print("Limit buy order placed successfully")
                # Display the order ID
                if "response" in result and "data" in result["response"] and "statuses" in result["response"]["data"]:
                    status = result["response"]["data"]["statuses"][0]
                    if "resting" in status:
                        oid = status["resting"]["oid"]
                        print(f"Order ID: {oid}")
            else:
                print(f"Limit buy order failed: {result.get('message', 'Unknown error')}")
                
        except Exception as e:
            print(f"\nError placing limit buy order: {str(e)}")
    
    def do_limit_sell(self, arg):
        """
        Place a limit sell order
        Usage: limit_sell <symbol> <size> <price>
        Example: limit_sell ETH 0.1 3500
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            args = arg.split()
            if len(args) < 3:
                print("Invalid arguments. Usage: limit_sell <symbol> <size> <price>")
                return
                
            symbol = args[0]
            size = float(args[1])
            price = float(args[2])
            
            print(f"\nPlacing limit sell order: {size} {symbol} @ {price}")
            result = self.order_handler.limit_sell(symbol, size, price)
            
            if result["status"] == "ok":
                print("Limit sell order placed successfully")
                # Display the order ID
                if "response" in result and "data" in result["response"] and "statuses" in result["response"]["data"]:
                    status = result["response"]["data"]["statuses"][0]
                    if "resting" in status:
                        oid = status["resting"]["oid"]
                        print(f"Order ID: {oid}")
            else:
                print(f"Limit sell order failed: {result.get('message', 'Unknown error')}")
                
        except Exception as e:
            print(f"\nError placing limit sell order: {str(e)}")

    # =================================Perp Trading==============================================

    def do_perp_buy(self, arg):
        """
        Execute a perpetual market buy order
        Usage: perp_buy <symbol> <size> [leverage] [slippage]
        Example: perp_buy BTC 0.01 5 0.03
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            args = arg.split()
            if len(args) < 2:
                print("Invalid arguments. Usage: perp_buy <symbol> <size> [leverage] [slippage]")
                return
                
            symbol = args[0]
            size = float(args[1])
            leverage = int(args[2]) if len(args) > 2 else 1
            slippage = float(args[3]) if len(args) > 3 else 0.05
            
            print(f"\nExecuting perp market buy: {size} {symbol} with {leverage}x leverage (slippage: {slippage*100}%)")
            result = self.order_handler.perp_market_buy(symbol, size, leverage, slippage)
            
            if result["status"] == "ok":
                print("Perpetual market buy order executed successfully")
                # Display the details
                if "response" in result and "data" in result["response"] and "statuses" in result["response"]["data"]:
                    for status in result["response"]["data"]["statuses"]:
                        if "filled" in status:
                            filled = status["filled"]
                            print(f"Filled: {filled['totalSz']} @ {filled['avgPx']}")
            else:
                print(f"Perpetual market buy order failed: {result.get('message', 'Unknown error')}")
                
        except Exception as e:
            print(f"\nError executing perpetual market buy: {str(e)}")

    def do_perp_sell(self, arg):
        """
        Execute a perpetual market sell order
        Usage: perp_sell <symbol> <size> [leverage] [slippage]
        Example: perp_sell BTC 0.01 5 0.03
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            args = arg.split()
            if len(args) < 2:
                print("Invalid arguments. Usage: perp_sell <symbol> <size> [leverage] [slippage]")
                return
                
            symbol = args[0]
            size = float(args[1])
            leverage = int(args[2]) if len(args) > 2 else 1
            slippage = float(args[3]) if len(args) > 3 else 0.05
            
            print(f"\nExecuting perp market sell: {size} {symbol} with {leverage}x leverage (slippage: {slippage*100}%)")
            result = self.order_handler.perp_market_sell(symbol, size, leverage, slippage)
            
            if result["status"] == "ok":
                print("Perpetual market sell order executed successfully")
                # Display the details
                if "response" in result and "data" in result["response"] and "statuses" in result["response"]["data"]:
                    for status in result["response"]["data"]["statuses"]:
                        if "filled" in status:
                            filled = status["filled"]
                            print(f"Filled: {filled['totalSz']} @ {filled['avgPx']}")
            else:
                print(f"Perpetual market sell order failed: {result.get('message', 'Unknown error')}")
                
        except Exception as e:
            print(f"\nError executing perpetual market sell: {str(e)}")

    def do_perp_limit_buy(self, arg):
        """
        Place a perpetual limit buy order
        Usage: perp_limit_buy <symbol> <size> <price> [leverage]
        Example: perp_limit_buy BTC 0.01 50000 5
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            args = arg.split()
            if len(args) < 3:
                print("Invalid arguments. Usage: perp_limit_buy <symbol> <size> <price> [leverage]")
                return
                
            symbol = args[0]
            size = float(args[1])
            price = float(args[2])
            leverage = int(args[3]) if len(args) > 3 else 1
            
            print(f"\nPlacing perp limit buy order: {size} {symbol} @ {price} with {leverage}x leverage")
            result = self.order_handler.perp_limit_buy(symbol, size, price, leverage)
            
            if result["status"] == "ok":
                print("Perpetual limit buy order placed successfully")
                # Display the order ID
                if "response" in result and "data" in result["response"] and "statuses" in result["response"]["data"]:
                    status = result["response"]["data"]["statuses"][0]
                    if "resting" in status:
                        oid = status["resting"]["oid"]
                        print(f"Order ID: {oid}")
            else:
                print(f"Perpetual limit buy order failed: {result.get('message', 'Unknown error')}")
                
        except Exception as e:
            print(f"\nError placing perpetual limit buy order: {str(e)}")

    def do_perp_limit_sell(self, arg):
        """
        Place a perpetual limit sell order
        Usage: perp_limit_sell <symbol> <size> <price> [leverage]
        Example: perp_limit_sell BTC 0.01 60000 5
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            args = arg.split()
            if len(args) < 3:
                print("Invalid arguments. Usage: perp_limit_sell <symbol> <size> <price> [leverage]")
                return
                
            symbol = args[0]
            size = float(args[1])
            price = float(args[2])
            leverage = int(args[3]) if len(args) > 3 else 1
            
            print(f"\nPlacing perp limit sell order: {size} {symbol} @ {price} with {leverage}x leverage")
            result = self.order_handler.perp_limit_sell(symbol, size, price, leverage)
            
            if result["status"] == "ok":
                print("Perpetual limit sell order placed successfully")
                # Display the order ID
                if "response" in result and "data" in result["response"] and "statuses" in result["response"]["data"]:
                    status = result["response"]["data"]["statuses"][0]
                    if "resting" in status:
                        oid = status["resting"]["oid"]
                        print(f"Order ID: {oid}")
            else:
                print(f"Perpetual limit sell order failed: {result.get('message', 'Unknown error')}")
                
        except Exception as e:
            print(f"\nError placing perpetual limit sell order: {str(e)}")
# ===================Close Position============================
    def do_close_position(self, arg):
        """
        Close an entire perpetual position
        Usage: close_position <symbol> [slippage]
        Example: close_position BTC 0.03
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            args = arg.split()
            if len(args) < 1:
                print("Invalid arguments. Usage: close_position <symbol> [slippage]")
                return
                
            symbol = args[0]
            slippage = float(args[1]) if len(args) > 1 else 0.05
            
            print(f"\nClosing position for {symbol} (slippage: {slippage*100}%)")
            result = self.order_handler.close_position(symbol, slippage)
            
            if result["status"] == "ok":
                print("Position closed successfully")
                # Display the details
                if "response" in result and "data" in result["response"] and "statuses" in result["response"]["data"]:
                    for status in result["response"]["data"]["statuses"]:
                        if "filled" in status:
                            filled = status["filled"]
                            print(f"Filled: {filled['totalSz']} @ {filled['avgPx']}")
            else:
                print(f"Position close failed: {result.get('message', 'Unknown error')}")
                
        except Exception as e:
            print(f"\nError closing position: {str(e)}")

# ============================ Leverage Setting ===============================

    def do_set_leverage(self, arg):
        """
        Set leverage for a symbol
        Usage: set_leverage <symbol> <leverage>
        Example: set_leverage BTC 5
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            args = arg.split()
            if len(args) < 2:
                print("Invalid arguments. Usage: set_leverage <symbol> <leverage>")
                return
                
            symbol = args[0]
            leverage = int(args[1])
            
            print(f"\nSetting {leverage}x leverage for {symbol}")
            result = self.order_handler._set_leverage(symbol, leverage)
            
            if result["status"] == "ok":
                print(f"Leverage for {symbol} set to {leverage}x")
            else:
                print(f"Failed to set leverage: {result.get('message', 'Unknown error')}")
                
        except Exception as e:
            print(f"\nError setting leverage: {str(e)}")

    # ================================Cancellation of Orders=====================================
    
    def do_cancel(self, arg):
        """
        Cancel a specific order
        Usage: cancel <symbol> <order_id>
        Example: cancel ETH 123456
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            args = arg.split()
            if len(args) < 2:
                print("Invalid arguments. Usage: cancel <symbol> <order_id>")
                return
                
            symbol = args[0]
            order_id = int(args[1])
            
            print(f"\nCancelling order {order_id} for {symbol}")
            result = self.order_handler.cancel_order(symbol, order_id)
            
            if result["status"] == "ok":
                print(f"Order {order_id} cancelled successfully")
            else:
                print(f"Failed to cancel order: {result.get('message', 'Unknown error')}")
                
        except Exception as e:
            print(f"\nError cancelling order: {str(e)}")
    
    def do_cancel_all(self, arg):
        """
        Cancel all open orders, optionally for a specific symbol
        Usage: cancel_all [symbol]
        Example: cancel_all ETH
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            symbol = arg.strip() if arg.strip() else None
            symbol_text = f" for {symbol}" if symbol else ""
            
            print(f"\nCancelling all orders{symbol_text}")
            result = self.order_handler.cancel_all_orders(symbol)
            
            if result["status"] == "ok":
                cancelled = result["data"]["cancelled"]
                failed = result["data"]["failed"]
                print(f"Cancelled {cancelled} orders, {failed} failed")
            else:
                print(f"Failed to cancel orders: {result.get('message', 'Unknown error')}")
                
        except Exception as e:
            print(f"\nError cancelling orders: {str(e)}")
    
    def do_orders(self, arg):
        """
        List all open orders, optionally for a specific symbol
        Usage: orders [symbol]
        Example: orders ETH
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            symbol = arg.strip() if arg.strip() else None
            symbol_text = f" for {symbol}" if symbol else ""
            
            print(f"\n=== Open Orders{symbol_text} ===")
            open_orders = self.order_handler.get_open_orders(symbol)
            
            if open_orders:
                headers = ["Symbol", "Side", "Size", "Price", "Order ID", "Timestamp"]
                rows = []
                
                for order in open_orders:
                    timestamp = datetime.fromtimestamp(order.get("timestamp", 0) / 1000).strftime("%Y-%m-%d %H:%M:%S")
                    rows.append([
                        order.get("coin", ""),
                        "Buy" if order.get("side", "") == "B" else "Sell",
                        float(order.get("sz", 0)),
                        float(order.get("limitPx", 0)),
                        order.get("oid", 0),
                        timestamp
                    ])
                
                self._print_table(headers, rows)
            else:
                print("No open orders")
                
        except Exception as e:
            print(f"\nError fetching open orders: {str(e)}")
    
    def do_positions(self, arg):
        """
        Show current positions
        Usage: positions
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            print("\n=== Current Positions ===")
            positions = []
            
            perp_state = self.api_connector.info.user_state(self.api_connector.wallet_address)
            for asset_position in perp_state.get("assetPositions", []):
                position = asset_position.get("position", {})
                if float(position.get("szi", 0)) != 0:
                    positions.append({
                        "symbol": position.get("coin", ""),
                        "size": float(position.get("szi", 0)),
                        "entry_price": float(position.get("entryPx", 0)),
                        "mark_price": float(position.get("markPx", 0)),
                        "liquidation_price": float(position.get("liquidationPx", 0) or 0),
                        "unrealized_pnl": float(position.get("unrealizedPnl", 0)),
                        "margin_used": float(position.get("marginUsed", 0))
                    })
            
            if positions:
                headers = ["Symbol", "Size", "Entry Price", "Mark Price", "Unrealized PnL", "Margin Used"]
                rows = []
                
                for pos in positions:
                    rows.append([
                        pos["symbol"],
                        pos["size"],
                        pos["entry_price"],
                        pos["mark_price"],
                        pos["unrealized_pnl"],
                        pos["margin_used"]
                    ])
                
                self._print_table(headers, rows)
            else:
                print("No open positions")
                
        except Exception as e:
            print(f"\nError fetching positions: {str(e)}")
    
    def do_history(self, arg):
        """
        Show trading history
        Usage: history [limit]
        Example: history 10
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            limit = int(arg) if arg.isdigit() else 20
            
            print(f"\n=== Trading History (Last {limit} Trades) ===")
            
            fills = []
            try:
                with open("fills", "r") as f:
                    for line in f:
                        fills.extend(json.loads(line.strip()))
            except FileNotFoundError:
                print("No trading history found")
                return
            
            if fills:
                headers = ["Time", "Symbol", "Side", "Size", "Price", "PnL"]
                rows = []
                
                for fill in fills[-limit:]:
                    time_str = datetime.fromtimestamp(fill["time"] / 1000).strftime("%Y-%m-%d %H:%M:%S")
                    rows.append([
                        time_str,
                        fill["coin"],
                        "Buy" if fill["side"] == "B" else "Sell",
                        float(fill["sz"]),
                        float(fill["px"]),
                        float(fill.get("closedPnl", 0))
                    ])
                
                self._print_table(headers, rows)
            else:
                print("No trades found")
                
        except Exception as e:
            print(f"\nError fetching history: {str(e)}")
    
    def do_clear(self, arg):
        """Clear the terminal screen"""
        self.display_layout()
    
    def do_exit(self, arg):
        """To exit type 'EOF' or 'exit' or Ctrl+D"""
        print("\nThank you for using MMMM Trading Bot!")
        return True
        
    def do_EOF(self, arg):
        """To exit type 'EOF' or 'exit' or Ctrl+D"""
        return self.do_exit(arg)
    
    def _print_table(self, headers, rows):
        """Print a formatted table to the console"""
        # Calculate column widths
        col_widths = [len(str(h)) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                col_widths[i] = max(col_widths[i], len(str(cell)))
        
        # Print headers
        header_str = " | ".join(str(h).ljust(col_widths[i]) for i, h in enumerate(headers))
        print(header_str)
        print("-" * len(header_str))
        
        # Print rows
        for row in rows:
            row_str = " | ".join(str(cell).ljust(col_widths[i]) for i, cell in enumerate(row))
            print(row_str)

    # =====================================Strategy Selector=========================================

    # These methods should be added to the MMMMTerminalUI class in terminal_ui.py

    def __init__(self, api_connector, order_handler, config_manager):
        super().__init__()
        self.prompt = '>>> '
        self.api_connector = api_connector
        self.order_handler = order_handler
        self.config_manager = config_manager
        self.authenticated = False
        self.last_command_output = ""
        
        # Initialize strategy selector
        from strategy_selector import StrategySelector
        self.strategy_selector = StrategySelector(api_connector, order_handler, config_manager)

    def do_select_strategy(self, arg):
        """
        Select and configure a trading strategy
        Usage: select_strategy [strategy_name]
        Example: select_strategy pure_mm
        
        If no strategy name is provided, a list of available strategies will be displayed.
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            # If no specific strategy is provided, list available strategies
            if not arg.strip():
                strategies = self.strategy_selector.list_strategies()
                
                if not strategies:
                    print("\nNo trading strategies available.")
                    print("Please make sure strategy files are in the 'strategies' directory.")
                    return
                
                print("\n=== Available Trading Strategies ===")
                
                for i, strategy in enumerate(strategies):
                    print(f"{i+1}. {strategy['name']}")
                    print(f"   Module: {strategy['module']}")
                    print(f"   Description: {strategy['description']}")
                    print()
                
                print("To select a strategy, use: select_strategy <module_name>")
                print("Example: select_strategy pure_mm")
                return
            
            # A specific strategy was requested
            strategy_name = arg.strip()
            
            # Check if strategy exists
            strategies = self.strategy_selector.list_strategies()
            strategy_exists = any(s['module'] == strategy_name for s in strategies)
            
            if not strategy_exists:
                print(f"\nStrategy '{strategy_name}' not found.")
                print("Use 'select_strategy' to see available strategies.")
                return
            
            # Get strategy parameters
            params = self.strategy_selector.get_strategy_params(strategy_name)
            
            if not params:
                print(f"\nStrategy '{strategy_name}' has no configurable parameters.")
                
                # Confirm starting with default parameters
                confirm = input("Do you want to start this strategy with default settings? (y/n): ")
                if confirm.lower() == 'y':
                    success = self.strategy_selector.start_strategy(strategy_name)
                    if success:
                        print(f"\nStarted strategy: {strategy_name}")
                        print("Use 'strategy_status' to check status.")
                        print("Use 'stop_strategy' to stop the strategy.")
                    else:
                        print(f"\nFailed to start strategy: {strategy_name}")
                return
            
            # Show current parameters and allow customization
            print(f"\n=== '{strategy_name}' Parameters ===")
            
            # Display parameters in a more user-friendly way
            for param_name, param_data in params.items():
                if isinstance(param_data, dict) and "value" in param_data:
                    value = param_data["value"]
                    description = param_data.get("description", "")
                    print(f"{param_name}: {value} - {description}")
                else:
                    print(f"{param_name}: {param_data}")
            
            # Ask if user wants to customize
            customize = input("\nDo you want to customize these parameters? (y/n): ")
            
            custom_params = {}
            
            if customize.lower() == 'y':
                for param_name, param_data in params.items():
                    if isinstance(param_data, dict) and "value" in param_data:
                        current_value = param_data["value"]
                        param_type = param_data.get("type", "str")
                        description = param_data.get("description", "")
                        
                        # Show the current value and description
                        prompt = f"{param_name} ({description}) [{current_value}]: "
                        
                        # Get user input
                        user_input = input(prompt)
                        
                        # Use current value if no input
                        if not user_input.strip():
                            custom_params[param_name] = {"value": current_value}
                            continue
                        
                        # Convert input to the correct type
                        try:
                            if param_type == "float":
                                value = float(user_input)
                            elif param_type == "int":
                                value = int(user_input)
                            elif param_type == "bool":
                                value = user_input.lower() in ('yes', 'true', 't', 'y', '1')
                            else:
                                value = user_input
                            
                            custom_params[param_name] = {"value": value}
                        except ValueError:
                            print(f"Invalid value for {param_name}. Using default: {current_value}")
                            custom_params[param_name] = {"value": current_value}
                    else:
                        # Simple parameter without metadata
                        current_value = param_data
                        prompt = f"{param_name} [{current_value}]: "
                        user_input = input(prompt)
                        
                        if not user_input.strip():
                            custom_params[param_name] = current_value
                        else:
                            custom_params[param_name] = user_input
            else:
                # Use default parameters
                for param_name, param_data in params.items():
                    if isinstance(param_data, dict) and "value" in param_data:
                        custom_params[param_name] = {"value": param_data["value"]}
                    else:
                        custom_params[param_name] = param_data
            
            # Confirm starting the strategy
            confirm = input("\nStart strategy with these parameters? (y/n): ")
            if confirm.lower() == 'y':
                success = self.strategy_selector.start_strategy(strategy_name, custom_params)
                if success:
                    print(f"\nStarted strategy: {strategy_name}")
                    print("Use 'strategy_status' to check status.")
                    print("Use 'stop_strategy' to stop the strategy.")
                else:
                    print(f"\nFailed to start strategy: {strategy_name}")
            
        except Exception as e:
            print(f"\nError selecting strategy: {str(e)}")

    def do_strategy_status(self, arg):
        """
        Check the status of the currently running strategy
        Usage: strategy_status
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            active_strategy = self.strategy_selector.get_active_strategy()
            
            if not active_strategy:
                print("\nNo active trading strategy running.")
                print("Use 'select_strategy' to start a strategy.")
                return
            
            print(f"\n=== Active Strategy: {active_strategy['name']} ===")
            print(f"Module: {active_strategy['module']}")
            print(f"Status: {'Running' if active_strategy['running'] else 'Stopped'}")
            
            # Get strategy instance for more detailed status
            strategy_instance = self.strategy_selector.active_strategy["instance"]
            
            if hasattr(strategy_instance, 'get_status'):
                print(f"Current state: {strategy_instance.get_status()}")
            
            if hasattr(strategy_instance, 'get_performance_metrics'):
                metrics = strategy_instance.get_performance_metrics()
                if metrics:
                    print("\nPerformance Metrics:")
                    for key, value in metrics.items():
                        print(f"  {key}: {value}")
            
        except Exception as e:
            print(f"\nError checking strategy status: {str(e)}")

    def do_stop_strategy(self, arg):
        """
        Stop the currently running strategy
        Usage: stop_strategy
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            active_strategy = self.strategy_selector.get_active_strategy()
            
            if not active_strategy:
                print("\nNo active trading strategy to stop.")
                return
            
            print(f"\nStopping strategy: {active_strategy['name']}")
            
            success = self.strategy_selector.stop_strategy()
            
            if success:
                print("Strategy stopped successfully.")
            else:
                print("Failed to stop strategy.")
            
        except Exception as e:
            print(f"\nError stopping strategy: {str(e)}")

    def do_strategy_params(self, arg):
        """
        View or modify parameters of a strategy
        Usage: strategy_params [strategy_name]
        
        If no strategy name is provided, shows parameters of the active strategy.
        """
        if not self.api_connector.exchange:
            print("Not connected to exchange. Use 'connect' first.")
            return
            
        try:
            strategy_name = arg.strip()
            
            # If no strategy name provided, use active strategy
            if not strategy_name:
                active_strategy = self.strategy_selector.get_active_strategy()
                
                if not active_strategy:
                    print("\nNo active strategy. Specify a strategy name or start a strategy first.")
                    return
                
                strategy_name = active_strategy['module']
            
            # Get strategy parameters
            params = self.strategy_selector.get_strategy_params(strategy_name)
            
            if not params:
                print(f"\nStrategy '{strategy_name}' has no configurable parameters or doesn't exist.")
                return
            
            print(f"\n=== '{strategy_name}' Parameters ===")
            
            for param_name, param_data in params.items():
                if isinstance(param_data, dict) and "value" in param_data:
                    value = param_data["value"]
                    description = param_data.get("description", "")
                    print(f"{param_name}: {value} - {description}")
                else:
                    print(f"{param_name}: {param_data}")
            
        except Exception as e:
            print(f"\nError getting strategy parameters: {str(e)}")

    def do_help_strategies(self, arg):
        """
        Show help for trading strategies
        Usage: help_strategies
        """
        print("\n=== Trading Strategies Help ===")
        print("\nMMMM supports various automated trading strategies.")
        print("You can select, configure, and monitor these strategies using these commands:")
        
        print("\nCommands:")
        print("  select_strategy     - Select and configure a trading strategy")
        print("  strategy_status     - Check the status of the currently running strategy")
        print("  stop_strategy       - Stop the currently running strategy")
        print("  strategy_params     - View parameters of a strategy")
        
        print("\nBasic Workflow:")
        print("  1. Connect to the exchange using 'connect'")
        print("  2. View available strategies with 'select_strategy'")
        print("  3. Select and configure a strategy with 'select_strategy <name>'")
        print("  4. Monitor the strategy with 'strategy_status'")
        print("  5. Stop the strategy when done with 'stop_strategy'")
        
        print("\nAvailable Strategies:")
        strategies = self.strategy_selector.list_strategies()
        
        if not strategies:
            print("  No trading strategies available.")
            print("  Please make sure strategy files are in the 'strategies' directory.")
            return
        
        for strategy in strategies:
            print(f"  - {strategy['name']} ({strategy['module']})")
            print(f"    {strategy['description']}")