class BybitConnector:
    """Handles connections to Bybit API and exchanges"""
    
    def __init__(self, api_key=None, api_secret=None, testnet=False):
        self.logger = logging.getLogger(__name__)
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.session = None
        self.ws = None
        # Initialize connection state variables
        self.connected = False
        
    def connect(self):
        """Initialize HTTP and WebSocket connections to Bybit"""
        try:
            from pybit.unified_trading import HTTP, WebSocket
            
            # Initialize HTTP session
            self.session = HTTP(
                testnet=self.testnet,
                api_key=self.api_key,
                api_secret=self.api_secret
            )
            
            # Test connection by getting server time
            server_time = self.session.get_server_time()
            if server_time["retCode"] == 0:
                self.connected = True
                self.logger.info(f"Successfully connected to Bybit {'(testnet)' if self.testnet else ''}")
                return True
            else:
                self.logger.error(f"Failed to connect to Bybit: {server_time}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error connecting to Bybit: {str(e)}")
            return False
            
    def get_balances(self):
        """Get all balances from Bybit"""
        if not self.session:
            self.logger.error("Not connected to Bybit")
            return {"spot": [], "perp": {}}
            
        try:
            # Get wallet balance for both spot and futures
            response = self.session.get_wallet_balance(accountType="UNIFIED")
            
            if response["retCode"] != 0:
                self.logger.error(f"Error fetching balances: {response['retMsg']}")
                return {"spot": [], "perp": {}}
                
            # Format balances to match Hyperliquid format
            spot_balances = []
            perp_balances = {}
            
            # Process the balances
            for coin in response["result"]["list"][0]["coin"]:
                spot_balances.append({
                    "asset": coin["coin"],
                    "available": float(coin["availableToWithdraw"]),
                    "total": float(coin["walletBalance"]),
                    "in_orders": float(coin["walletBalance"]) - float(coin["availableToWithdraw"])
                })
                
            return {
                "spot": spot_balances,
                "perp": perp_balances
            }
            
        except Exception as e:
            self.logger.error(f"Error fetching balances: {str(e)}")
            return {"spot": [], "perp": {}}
            
    def get_market_data(self, symbol):
        """
        Get market data for a specific symbol with robust error handling
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            Dict with market data including mid_price, best_bid, best_ask
        """
        if not self.session:
            self.logger.error(f"Not connected to Bybit when getting market data for {symbol}")
            return {"error": "Not connected"}
            
        try:
            # Get orderbook
            response = self.session.get_orderbook(
                category="linear",  # Assuming USDT perpetuals
                symbol=symbol,
                limit=50
            )
            
            if response["retCode"] != 0:
                self.logger.error(f"Error getting orderbook: {response['retMsg']}")
                return {"error": response["retMsg"]}
                
            orderbook = response["result"]
            
            # Extract best bid and ask
            if len(orderbook["b"]) > 0 and len(orderbook["a"]) > 0:
                best_bid = float(orderbook["b"][0][0])
                best_ask = float(orderbook["a"][0][0])
                mid_price = (best_bid + best_ask) / 2
                
                market_data = {
                    "best_bid": best_bid,
                    "best_ask": best_ask,
                    "mid_price": mid_price,
                    "order_book": orderbook
                }
                
                return market_data
            else:
                self.logger.error(f"Empty orderbook for {symbol}")
                return {"error": "Empty orderbook"}
                
        except Exception as e:
            self.logger.error(f"Error getting market data for {symbol}: {str(e)}")
            return {"error": str(e)}
            
    # Add other methods similar to api_connector.py but for Bybit

    def init_websocket(self, symbols):
        """Initialize WebSocket connections for specified symbols"""
        try:
            from pybit.unified_trading import WebSocket
            
            self.ws = WebSocket(
                testnet=self.testnet,
                channel_type="linear"  # For USDT perpetuals
            )
            
            self.logger.info(f"WebSocket initialized for {len(symbols)} symbols")
            return True
            
        except Exception as e:
            self.logger.error(f"Error initializing WebSocket: {str(e)}")
            return False
            
    def subscribe_orderbook(self, symbol, callback):
        """Subscribe to orderbook for a symbol"""
        if not self.ws:
            self.logger.error("WebSocket not initialized")
            return False
            
        try:
            # Subscribe to orderbook with depth of 50
            self.ws.orderbook_stream(50, symbol, callback)
            self.logger.info(f"Subscribed to orderbook for {symbol}")
            return True
        except Exception as e:
            self.logger.error(f"Error subscribing to orderbook: {str(e)}")
            return False