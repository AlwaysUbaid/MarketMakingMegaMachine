import logging
from typing import Dict, Optional, Any, List
import hyperliquid
import time

import eth_account
from eth_account.signers.local import LocalAccount
from hyperliquid.exchange import Exchange
from hyperliquid.info import Info
from hyperliquid.utils import constants

class ApiConnector:
    """Handles connections to trading APIs and exchanges"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.wallet: Optional[LocalAccount] = None
        self.wallet_address: Optional[str] = None
        self.exchange: Optional[Exchange] = None
        self.info: Optional[Info] = None
        
    def connect_hyperliquid(self, wallet_address: str, secret_key: str, 
                           use_testnet: bool = False) -> bool:
        """
        Connect to Hyperliquid exchange
        
        Args:
            wallet_address: Wallet address for authentication
            secret_key: Secret key for authentication 
            use_testnet: Whether to use testnet (default is mainnet)
            
        Returns:
            True if connected successfully, False otherwise
        """
        try:
            self.wallet_address = wallet_address
            api_url = constants.TESTNET_API_URL if use_testnet else constants.MAINNET_API_URL
            
            # Initialize wallet
            self.wallet = eth_account.Account.from_key(secret_key)
            
            # Initialize exchange and info
            self.exchange = Exchange(
                self.wallet,
                api_url,
                account_address=self.wallet_address
            )
            self.info = Info(api_url)
            
            # Test connection by getting balances
            user_state = self.info.user_state(self.wallet_address)
            
            self.logger.info(f"Successfully connected to Hyperliquid {'(testnet)' if use_testnet else ''}")
            return True
        except Exception as e:
            self.logger.error(f"Error connecting to Hyperliquid: {str(e)}")
            return False
    
    def get_balances(self) -> Dict[str, Any]:
        """Get all balances (spot and perpetual)"""
        if not self.info or not self.wallet_address:
            self.logger.error("Not connected to exchange")
            return {"spot": [], "perp": {}}
        
        try:
            spot_state = self.info.spot_user_state(self.wallet_address)
            perp_state = self.info.user_state(self.wallet_address)
            
            # Format spot balances
            spot_balances = []
            for balance in spot_state.get("balances", []):
                spot_balances.append({
                    "asset": balance.get("coin", ""),
                    "available": float(balance.get("available", 0)),
                    "total": float(balance.get("total", 0)),
                    "in_orders": float(balance.get("total", 0)) - float(balance.get("available", 0))
                })
            
            # Format perpetual balances
            margin_summary = perp_state.get("marginSummary", {})
            perp_balances = {
                "account_value": float(margin_summary.get("accountValue", 0)),
                "margin_used": float(margin_summary.get("totalMarginUsed", 0)),
                "position_value": float(margin_summary.get("totalNtlPos", 0))
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
        if not self.info or not self.wallet_address:
            self.logger.error("Not connected to exchange")
            return []
        
        try:
            perp_state = self.info.user_state(self.wallet_address)
            positions = []
            
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
        if not self.info:
            self.logger.error(f"Not connected to exchange when getting market data for {symbol}")
            return {}
        
        try:
            # Try multiple methods to get price data for maximum reliability
            market_data = {}
            
            # Method 1: Get order book
            try:
                order_book = self.info.l2_snapshot(symbol)
                
                if order_book and "levels" in order_book and len(order_book["levels"]) >= 2:
                    bid_levels = order_book["levels"][0]
                    ask_levels = order_book["levels"][1]
                    
                    if bid_levels and len(bid_levels) > 0:
                        market_data["best_bid"] = float(bid_levels[0]["px"])
                    
                    if ask_levels and len(ask_levels) > 0:
                        market_data["best_ask"] = float(ask_levels[0]["px"])
                    
                    # Calculate mid price if we have both bid and ask
                    if "best_bid" in market_data and "best_ask" in market_data:
                        market_data["mid_price"] = (market_data["best_bid"] + market_data["best_ask"]) / 2
                        self.logger.info(f"Got price for {symbol} from order book: {market_data['mid_price']}")
                
                market_data["order_book"] = order_book
            except Exception as e:
                self.logger.warning(f"Error getting order book for {symbol}: {str(e)}")
            
            # Method 2: Try all_mids if we don't have mid_price yet
            if "mid_price" not in market_data:
                try:
                    all_mids = self.info.all_mids()
                    mid_price = all_mids.get(symbol, None)
                    if mid_price is not None:
                        market_data["mid_price"] = float(mid_price)
                        self.logger.info(f"Got price for {symbol} from all_mids: {market_data['mid_price']}")
                except Exception as e:
                    self.logger.warning(f"Error getting all_mids for {symbol}: {str(e)}")
            
            # Method 3: Try metadata and last price if we still don't have a price
            if "mid_price" not in market_data:
                try:
                    meta = self.info.meta()
                    for asset in meta.get("universe", []):
                        if asset.get("name") == symbol:
                            last_price = asset.get("lastPrice")
                            if last_price:
                                market_data["mid_price"] = float(last_price)
                                self.logger.info(f"Got price for {symbol} from meta: {market_data['mid_price']}")
                                break
                except Exception as e:
                    self.logger.warning(f"Error getting meta for {symbol}: {str(e)}")
            
            # If we still don't have a price, try symbol info directly
            if "mid_price" not in market_data:
                try:
                    if hasattr(self.info, "ticker") and callable(self.info.ticker):
                        ticker = self.info.ticker(symbol)
                        if ticker and "last" in ticker:
                            market_data["mid_price"] = float(ticker["last"])
                            self.logger.info(f"Got price for {symbol} from ticker: {market_data['mid_price']}")
                except Exception as e:
                    self.logger.warning(f"Error getting ticker for {symbol}: {str(e)}")
            
            # Log if we still couldn't get a price
            if "mid_price" not in market_data:
                self.logger.error(f"Could not determine price for {symbol} using any method")
                return {"error": f"Could not determine price for {symbol}"}
            
            return market_data
        
        except Exception as e:
            self.logger.error(f"Error fetching market data for {symbol}: {str(e)}")
            return {"error": str(e)}
    
    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all open orders, optionally filtered by symbol"""
        if not self.info or not self.wallet_address:
            self.logger.error("Not connected to exchange")
            return []
        
        try:
            open_orders = self.info.open_orders(self.wallet_address)
            
            if symbol:
                open_orders = [order for order in open_orders if order["coin"] == symbol]
            
            return open_orders
        except Exception as e:
            self.logger.error(f"Error fetching open orders: {str(e)}")
            return []
    
    def get_trade_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent trade history"""
        if not self.info or not self.wallet_address:
            self.logger.error("Not connected to exchange")
            return []
        
        try:
            fills = self.info.user_fills(self.wallet_address)
            return fills[:limit]
        except Exception as e:
            self.logger.error(f"Error fetching trade history: {str(e)}")
            return []
    
    def get_candles(self, symbol: str, interval: str = "15m", start_time: Optional[int] = None, end_time: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get candle data for a symbol
        
        Args:
            symbol: Trading pair symbol
            interval: Candle interval (e.g., "15m", "1h", "4h", "1d")
            start_time: Start time in milliseconds (optional)
            end_time: End time in milliseconds (optional)
            
        Returns:
            List of candle data
        """
        if not self.info:
            self.logger.error("Not connected to exchange")
            return []
            
        try:
            # Calculate end time if not provided (current time)
            if not end_time:
                end_time = int(time.time() * 1000)  # Current time in milliseconds
            
            # Calculate start time if not provided (one candle before end time)
            if not start_time:
                # Parse interval to milliseconds
                interval_ms = self._parse_interval_to_ms(interval)
                start_time = end_time - interval_ms
            
            # Prepare request body
            req = {
                "type": "candleSnapshot",
                "req": {
                    "coin": symbol.replace("-PERP", ""),  # Remove -PERP suffix if present
                    "interval": interval,
                    "startTime": start_time,
                    "endTime": end_time
                }
            }
            
            # Make API request with proper headers
            headers = {
                "Content-Type": "application/json"
            }
            
            # Use the info object's session to make the request
            response = self.info.session.post(
                f"{self.info.base_url}/info",
                json=req,
                headers=headers
            )
            
            if response.status_code != 200:
                self.logger.error(f"Error fetching candles: {response.status_code} - {response.text}")
                return []
                
            data = response.json()
            if not data or not isinstance(data, list):
                self.logger.error(f"Invalid response format for candles: {data}")
                return []
                
            # Format candles
            candles = []
            for candle in data:
                try:
                    candles.append({
                        "timestamp": int(candle["t"]),
                        "open": float(candle["o"]),
                        "high": float(candle["h"]),
                        "low": float(candle["l"]),
                        "close": float(candle["c"]),
                        "volume": float(candle["v"])
                    })
                except (KeyError, ValueError) as e:
                    self.logger.warning(f"Error parsing candle data: {e}")
                    continue
                
            return candles
            
        except Exception as e:
            self.logger.error(f"Error fetching candles: {str(e)}")
            return []
            
    def _parse_interval_to_ms(self, interval: str) -> int:
        """Convert interval string to milliseconds"""
        try:
            unit = interval[-1]
            value = int(interval[:-1])
            
            if unit == 's':
                return value * 1000
            elif unit == 'm':
                return value * 60 * 1000
            elif unit == 'h':
                return value * 60 * 60 * 1000
            elif unit == 'd':
                return value * 24 * 60 * 60 * 1000
            else:
                raise ValueError(f"Invalid interval unit: {unit}")
        except Exception as e:
            self.logger.error(f"Error parsing interval: {str(e)}")
            return 60000  # Default to 1 minute