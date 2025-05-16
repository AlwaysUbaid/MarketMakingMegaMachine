import logging
from typing import Dict, Optional, Any, List
from pybit.unified_trading import HTTP, WebSocket

class BybitConnector:
    """Handles connections to Bybit trading API"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.http_client = None
        self.ws_public = None
        self.ws_private = None
        self.ws_trading = None
        self.api_key = None
        self.api_secret = None
        self.testnet = False
        self.connected = False
        self.wallet_address = None  # For API parity with HyperLiquid connector
        
    def connect_bybit(self, api_key: str, api_secret: str, 
                     use_testnet: bool = False, recv_window: int = 5000) -> bool:
        """
        Connect to Bybit exchange
        
        Args:
            api_key: API key for authentication
            api_secret: API secret for authentication
            use_testnet: Whether to use testnet (default is mainnet)
            recv_window: Receive window for requests in milliseconds
            
        Returns:
            True if connected successfully, False otherwise
        """
        try:
            self.api_key = api_key
            self.api_secret = api_secret
            self.testnet = use_testnet
            self.wallet_address = f"bybit:{api_key[:8]}..."  # Use truncated API key as wallet identifier
            
            # Initialize HTTP client
            self.http_client = HTTP(
                testnet=use_testnet,
                api_key=api_key,
                api_secret=api_secret,
                recv_window=recv_window,
                logging_level=logging.INFO
            )
            
            # Initialize WebSocket connections
            # We'll connect them on-demand to save resources
            
            # Test connection by getting wallet balance
            try:
                account_info = self.http_client.get_account_info()
                if account_info["retCode"] == 0:
                    self.connected = True
                    self.logger.info(f"Successfully connected to Bybit {'(testnet)' if use_testnet else ''}")
                    return True
                else:
                    self.logger.error(f"Failed to connect to Bybit: {account_info['retMsg']}")
                    return False
            except Exception as e:
                self.logger.error(f"Error testing Bybit connection: {str(e)}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error connecting to Bybit: {str(e)}")
            return False
    
    def get_balances(self) -> Dict[str, Any]:
        """Get all balances (spot and perpetual)"""
        if not self.http_client or not self.connected:
            self.logger.error("Not connected to exchange")
            return {"spot": [], "perp": {}}
        
        try:
            # Get unified account balance
            unified_balance = self.http_client.get_wallet_balance(accountType="UNIFIED")
            
            # Get USDT perpetual account balance if available
            try:
                usdt_perp_balance = self.http_client.get_wallet_balance(accountType="CONTRACT")
            except:
                usdt_perp_balance = {"result": {"list": []}}
            
            # Format spot balances
            spot_balances = []
            if unified_balance["retCode"] == 0:
                for account in unified_balance["result"]["list"]:
                    for coin in account.get("coin", []):
                        if float(coin.get("walletBalance", 0)) > 0:
                            spot_balances.append({
                                "asset": coin.get("coin", ""),
                                "available": float(coin.get("availableToWithdraw", 0)),
                                "total": float(coin.get("walletBalance", 0)),
                                "in_orders": float(coin.get("walletBalance", 0)) - float(coin.get("availableToWithdraw", 0))
                            })
            
            # Format perpetual balances
            perp_balances = {}
            account_value = 0
            margin_used = 0
            
            # Extract summary data from USDT perpetual account
            if usdt_perp_balance["retCode"] == 0:
                for account in usdt_perp_balance["result"]["list"]:
                    account_value += float(account.get("totalEquity", 0))
                    margin_used += float(account.get("totalInitialMargin", 0))
            
            # Also add data from unified account
            if unified_balance["retCode"] == 0:
                for account in unified_balance["result"]["list"]:
                    account_value += float(account.get("totalEquity", 0))
                    margin_used += float(account.get("totalInitialMargin", 0))
            
            perp_balances = {
                "account_value": account_value,
                "margin_used": margin_used,
                "position_value": margin_used  # Approximation
            }
            
            return {
                "spot": spot_balances,
                "perp": perp_balances
            }
        except Exception as e:
            self.logger.error(f"Error fetching balances: {str(e)}")
            return {"spot": [], "perp": {}}
    
    def get_positions(self) -> List[Dict[str, Any]]:
        """Get all open positions"""
        if not self.http_client or not self.connected:
            self.logger.error("Not connected to exchange")
            return []
        
        try:
            # Get positions for linear (USDT) perpetuals
            linear_positions = self.http_client.get_positions(category="linear")
            
            # Get positions for inverse contracts
            inverse_positions = self.http_client.get_positions(category="inverse")
            
            positions = []
            
            # Process linear positions
            if linear_positions["retCode"] == 0:
                for position in linear_positions["result"]["list"]:
                    if float(position.get("size", 0)) != 0:
                        positions.append({
                            "symbol": position.get("symbol", ""),
                            "size": float(position.get("size", 0)),
                            "entry_price": float(position.get("avgPrice", 0)),
                            "mark_price": float(position.get("markPrice", 0)),
                            "liquidation_price": float(position.get("liqPrice", 0) or 0),
                            "unrealized_pnl": float(position.get("unrealisedPnl", 0)),
                            "margin_used": float(position.get("positionIM", 0))
                        })
            
            # Process inverse positions
            if inverse_positions["retCode"] == 0:
                for position in inverse_positions["result"]["list"]:
                    if float(position.get("size", 0)) != 0:
                        positions.append({
                            "symbol": position.get("symbol", ""),
                            "size": float(position.get("size", 0)),
                            "entry_price": float(position.get("avgPrice", 0)),
                            "mark_price": float(position.get("markPrice", 0)),
                            "liquidation_price": float(position.get("liqPrice", 0) or 0),
                            "unrealized_pnl": float(position.get("unrealisedPnl", 0)),
                            "margin_used": float(position.get("positionIM", 0))
                        })
            
            return positions
        except Exception as e:
            self.logger.error(f"Error fetching positions: {str(e)}")
            return []
    
    def get_market_data(self, symbol: str) -> Dict[str, Any]:
        """
        Get market data for a specific symbol with robust error handling
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            Dict with market data including mid_price, best_bid, best_ask
        """
        if not self.http_client:
            self.logger.error(f"Not connected to exchange when getting market data for {symbol}")
            return {}
        
        try:
            market_data = {}
            category = self._determine_market_category(symbol)
            
            # Method 1: Get orderbook
            try:
                order_book = self.http_client.get_orderbook(category=category, symbol=symbol, limit=50)
                
                if order_book["retCode"] == 0 and "b" in order_book["result"] and "a" in order_book["result"]:
                    bids = order_book["result"]["b"]
                    asks = order_book["result"]["a"]
                    
                    if bids and len(bids) > 0:
                        market_data["best_bid"] = float(bids[0][0])
                    
                    if asks and len(asks) > 0:
                        market_data["best_ask"] = float(asks[0][0])
                    
                    # Calculate mid price if we have both bid and ask
                    if "best_bid" in market_data and "best_ask" in market_data:
                        market_data["mid_price"] = (market_data["best_bid"] + market_data["best_ask"]) / 2
                        self.logger.info(f"Got price for {symbol} from order book: {market_data['mid_price']}")
                
                market_data["order_book"] = order_book["result"]
            except Exception as e:
                self.logger.warning(f"Error getting order book for {symbol}: {str(e)}")
            
            # Method 2: Try tickers if we don't have mid_price yet
            if "mid_price" not in market_data:
                try:
                    tickers = self.http_client.get_tickers(category=category, symbol=symbol)
                    if tickers["retCode"] == 0 and "list" in tickers["result"] and len(tickers["result"]["list"]) > 0:
                        ticker = tickers["result"]["list"][0]
                        last_price = float(ticker.get("lastPrice", 0))
                        if last_price > 0:
                            market_data["mid_price"] = last_price
                            self.logger.info(f"Got price for {symbol} from ticker: {market_data['mid_price']}")
                            
                            # If we don't have best_bid/ask, also get them from ticker
                            if "best_bid" not in market_data:
                                market_data["best_bid"] = float(ticker.get("bid1Price", last_price))
                            if "best_ask" not in market_data:
                                market_data["best_ask"] = float(ticker.get("ask1Price", last_price))
                except Exception as e:
                    self.logger.warning(f"Error getting ticker for {symbol}: {str(e)}")
            
            # If we still don't have a price, log error
            if "mid_price" not in market_data:
                self.logger.error(f"Could not determine price for {symbol} using any method")
                return {"error": f"Could not determine price for {symbol}"}
            
            return market_data
        
        except Exception as e:
            self.logger.error(f"Error fetching market data for {symbol}: {str(e)}")
            return {"error": str(e)}
    
    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all open orders, optionally filtered by symbol"""
        if not self.http_client or not self.connected:
            self.logger.error("Not connected to exchange")
            return []
        
        try:
            all_orders = []
            
            # Get open orders for each category
            categories = ["spot", "linear", "inverse"]
            
            for category in categories:
                try:
                    if symbol:
                        orders = self.http_client.get_open_orders(
                            category=category,
                            symbol=symbol
                        )
                    else:
                        orders = self.http_client.get_open_orders(
                            category=category
                        )
                    
                    if orders["retCode"] == 0 and "list" in orders["result"]:
                        for order in orders["result"]["list"]:
                            # Convert to a format compatible with your existing system
                            normalized_order = {
                                "coin": order.get("symbol", ""),
                                "side": "B" if order.get("side", "") == "Buy" else "S",
                                "sz": float(order.get("qty", 0)),
                                "limitPx": float(order.get("price", 0)),
                                "oid": order.get("orderId", ""),
                                "timestamp": int(order.get("createdTime", 0))
                            }
                            all_orders.append(normalized_order)
                except Exception as e:
                    self.logger.warning(f"Error getting {category} orders: {str(e)}")
            
            return all_orders
        except Exception as e:
            self.logger.error(f"Error fetching open orders: {str(e)}")
            return []
    
    def get_trade_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent trade history"""
        if not self.http_client or not self.connected:
            self.logger.error("Not connected to exchange")
            return []
        
        try:
            all_trades = []
            
            # Get trade history for each category
            categories = ["spot", "linear", "inverse"]
            
            for category in categories:
                try:
                    # Using executions for trade history
                    trades = self.http_client.get_executions(
                        category=category,
                        limit=limit
                    )
                    
                    if trades["retCode"] == 0 and "list" in trades["result"]:
                        for trade in trades["result"]["list"]:
                            # Convert to a format compatible with your existing system
                            normalized_trade = {
                                "coin": trade.get("symbol", ""),
                                "side": "B" if trade.get("side", "") == "Buy" else "S",
                                "sz": float(trade.get("execQty", 0)),
                                "px": float(trade.get("execPrice", 0)),
                                "time": int(trade.get("execTime", 0)),
                                "closedPnl": float(trade.get("closedPnl", 0))
                            }
                            all_trades.append(normalized_trade)
                except Exception as e:
                    self.logger.warning(f"Error getting {category} trades: {str(e)}")
            
            # Sort by time in descending order
            all_trades.sort(key=lambda x: x.get("time", 0), reverse=True)
            
            # Limit the total number of trades
            return all_trades[:limit]
        except Exception as e:
            self.logger.error(f"Error fetching trade history: {str(e)}")
            return []

    def _determine_market_category(self, symbol: str) -> str:
        """
        Determine the market category for a symbol
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            Category string: "spot", "linear", or "inverse"
        """
        # Common patterns for symbol types
        if '/' in symbol:  # Like "BTC/USDT" - spot format
            return "spot"
        elif symbol.endswith("USDT"):  # Like "BTCUSDT" - linear perpetual
            return "linear"
        elif symbol.endswith("USD"):  # Like "BTCUSD" - inverse perpetual
            return "inverse"
        else:
            # Default to linear as most common
            return "linear"
    
    def _normalize_symbol(self, symbol: str, category: str) -> str:
        """
        Normalize symbol format for Bybit API
        
        Args:
            symbol: Symbol in any format
            category: Market category
            
        Returns:
            Properly formatted symbol for the category
        """
        if category == "spot" and '/' in symbol:
            # Convert "BTC/USDT" to "BTCUSDT"
            base, quote = symbol.split('/')
            return f"{base}{quote}"
        
        # For linear and inverse, return as is
        return symbol