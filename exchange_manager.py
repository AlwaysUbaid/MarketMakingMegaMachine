import logging
import threading
import time
from datetime import datetime

class ExchangeManager:
    """Coordinates multiple exchange connectors and operations"""
    
    def __init__(self, config_manager):
        self.logger = logging.getLogger(__name__)
        self.config = config_manager
        
        # Exchange connectors
        self.connectors = {}
        
        # Exchange order handlers
        self.order_handlers = {}
        
        # Lock for thread safety
        self.lock = threading.Lock()
        
        # Connection status
        self.connection_status = {}
        
    def add_exchange(self, exchange_id, connector, order_handler):
        """
        Add an exchange connector and order handler
        
        Args:
            exchange_id: Exchange identifier (e.g., "hyperliquid", "bybit")
            connector: Exchange connector instance
            order_handler: Order handler instance
        """
        with self.lock:
            self.connectors[exchange_id] = connector
            self.order_handlers[exchange_id] = order_handler
            self.connection_status[exchange_id] = False
            
    def connect_exchange(self, exchange_id):
        """
        Connect to a specific exchange
        
        Args:
            exchange_id: Exchange identifier
            
        Returns:
            bool: True if connected successfully
        """
        with self.lock:
            if exchange_id not in self.connectors:
                self.logger.error(f"Unknown exchange: {exchange_id}")
                return False
                
            connector = self.connectors[exchange_id]
            
            # Connect
            success = connector.connect()
            
            if success:
                self.connection_status[exchange_id] = True
                self.logger.info(f"Connected to {exchange_id}")
            else:
                self.connection_status[exchange_id] = False
                self.logger.error(f"Failed to connect to {exchange_id}")
                
            return success
            
    def connect_all(self):
        """
        Connect to all exchanges
        
        Returns:
            dict: Connection status for each exchange
        """
        results = {}
        
        for exchange_id in self.connectors:
            if self.config.is_exchange_enabled(exchange_id):
                results[exchange_id] = self.connect_exchange(exchange_id)
            else:
                self.logger.info(f"Exchange {exchange_id} is disabled, skipping connection")
                results[exchange_id] = False
                
        return results
        
    def disconnect_exchange(self, exchange_id):
        """
        Disconnect from a specific exchange
        
        Args:
            exchange_id: Exchange identifier
            
        Returns:
            bool: True if disconnected successfully
        """
        with self.lock:
            if exchange_id not in self.connectors:
                self.logger.error(f"Unknown exchange: {exchange_id}")
                return False
                
            connector = self.connectors[exchange_id]
            
            # Disconnect
            try:
                if hasattr(connector, 'disconnect'):
                    connector.disconnect()
                
                self.connection_status[exchange_id] = False
                self.logger.info(f"Disconnected from {exchange_id}")
                return True
            except Exception as e:
                self.logger.error(f"Error disconnecting from {exchange_id}: {str(e)}")
                return False
                
    def disconnect_all(self):
        """
        Disconnect from all exchanges
        
        Returns:
            dict: Disconnection status for each exchange
        """
        results = {}
        
        for exchange_id in self.connectors:
            results[exchange_id] = self.disconnect_exchange(exchange_id)
                
        return results
        
    def get_balances(self, exchange_id):
        """
        Get balances from a specific exchange
        
        Args:
            exchange_id: Exchange identifier
            
        Returns:
            dict: Balances from the exchange
        """
        if exchange_id not in self.connectors:
            self.logger.error(f"Unknown exchange: {exchange_id}")
            return {}
            
        if not self.connection_status[exchange_id]:
            self.logger.error(f"Not connected to {exchange_id}")
            return {}
            
        connector = self.connectors[exchange_id]
        
        try:
            return connector.get_balances()
        except Exception as e:
            self.logger.error(f"Error getting balances from {exchange_id}: {str(e)}")
            return {}
            
    def get_all_balances(self):
        """
        Get balances from all connected exchanges
        
        Returns:
            dict: Balances by exchange
        """
        results = {}
        
        for exchange_id, connected in self.connection_status.items():
            if connected:
                results[exchange_id] = self.get_balances(exchange_id)
                
        return results
        
    def get_market_data(self, exchange_id, symbol):
        """
        Get market data from a specific exchange
        
        Args:
            exchange_id: Exchange identifier
            symbol: Trading symbol
            
        Returns:
            dict: Market data from the exchange
        """
        if exchange_id not in self.connectors:
            self.logger.error(f"Unknown exchange: {exchange_id}")
            return {"error": "Unknown exchange"}
            
        if not self.connection_status[exchange_id]:
            self.logger.error(f"Not connected to {exchange_id}")
            return {"error": "Not connected"}
            
        connector = self.connectors[exchange_id]
        
        try:
            return connector.get_market_data(symbol)
        except Exception as e:
            self.logger.error(f"Error getting market data from {exchange_id} for {symbol}: {str(e)}")
            return {"error": str(e)}
            
    def place_order(self, exchange_id, order_type, symbol, side, size, price=None):
        """
        Place an order on a specific exchange
        
        Args:
            exchange_id: Exchange identifier
            order_type: Order type (e.g., "limit", "market")
            symbol: Trading symbol
            side: Order side (e.g., "buy", "sell")
            size: Order size
            price: Order price (for limit orders)
            
        Returns:
            dict: Order response
        """
        if exchange_id not in self.order_handlers:
            self.logger.error(f"Unknown exchange: {exchange_id}")
            return {"status": "error", "message": "Unknown exchange"}
            
        if not self.connection_status[exchange_id]:
            self.logger.error(f"Not connected to {exchange_id}")
            return {"status": "error", "message": "Not connected"}
            
        handler = self.order_handlers[exchange_id]
        
        try:
            if order_type.lower() == "limit":
                if not price:
                    return {"status": "error", "message": "Price required for limit orders"}
                    
                if side.lower() == "buy":
                    return handler.limit_buy(symbol, size, price)
                else:
                    return handler.limit_sell(symbol, size, price)
            elif order_type.lower() == "market":
                if side.lower() == "buy":
                    return handler.market_buy(symbol, size)
                else:
                    return handler.market_sell(symbol, size)
            else:
                return {"status": "error", "message": f"Unsupported order type: {order_type}"}
        except Exception as e:
            self.logger.error(f"Error placing order on {exchange_id}: {str(e)}")
            return {"status": "error", "message": str(e)}
            
    def cancel_order(self, exchange_id, symbol, order_id):
        """
        Cancel an order on a specific exchange
        
        Args:
            exchange_id: Exchange identifier
            symbol: Trading symbol
            order_id: Order ID to cancel
            
        Returns:
            dict: Cancellation response
        """
        if exchange_id not in self.order_handlers:
            self.logger.error(f"Unknown exchange: {exchange_id}")
            return {"status": "error", "message": "Unknown exchange"}
            
        if not self.connection_status[exchange_id]:
            self.logger.error(f"Not connected to {exchange_id}")
            return {"status": "error", "message": "Not connected"}
            
        handler = self.order_handlers[exchange_id]
        
        try:
            return handler.cancel_order(symbol, order_id)
        except Exception as e:
            self.logger.error(f"Error cancelling order on {exchange_id}: {str(e)}")
            return {"status": "error", "message": str(e)}
            
    def get_open_orders(self, exchange_id, symbol=None):
        """
        Get open orders from a specific exchange
        
        Args:
            exchange_id: Exchange identifier
            symbol: Optional symbol to filter orders
            
        Returns:
            list: Open orders
        """
        if exchange_id not in self.order_handlers:
            self.logger.error(f"Unknown exchange: {exchange_id}")
            return []
            
        if not self.connection_status[exchange_id]:
            self.logger.error(f"Not connected to {exchange_id}")
            return []
            
        handler = self.order_handlers[exchange_id]
        
        try:
            return handler.get_open_orders(symbol)
        except Exception as e:
            self.logger.error(f"Error getting open orders from {exchange_id}: {str(e)}")
            return []
            
    def is_connected(self, exchange_id):
        """
        Check if an exchange is connected
        
        Args:
            exchange_id: Exchange identifier
            
        Returns:
            bool: True if connected
        """
        return self.connection_status.get(exchange_id, False)