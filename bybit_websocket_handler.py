import logging
import threading
import time
from datetime import datetime

class BybitWebSocketHandler:
    """Handles WebSocket connections for Bybit"""
    
    def __init__(self, api_key=None, api_secret=None, testnet=False):
        self.logger = logging.getLogger(__name__)
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.ws = None
        self.callbacks = {}
        self.connected = False
        self.reconnect_count = 0
        self.max_reconnect = 10
        self.last_heartbeat = time.time()
        
    def connect(self):
        """Initialize WebSocket connection"""
        try:
            from pybit.unified_trading import WebSocket
            
            self.ws = WebSocket(
                testnet=self.testnet,
                channel_type="linear",
                api_key=self.api_key,
                api_secret=self.api_secret
            )
            
            self.connected = True
            self.last_heartbeat = time.time()
            self.logger.info(f"Connected to Bybit WebSocket {'(testnet)' if self.testnet else ''}")
            
            # Start heartbeat thread
            threading.Thread(target=self._heartbeat_checker, daemon=True).start()
            
            return True
        except Exception as e:
            self.logger.error(f"Error connecting to Bybit WebSocket: {str(e)}")
            self.connected = False
            return False
            
    def disconnect(self):
        """Close WebSocket connection"""
        if self.ws:
            try:
                # There is no explicit disconnect method in pybit WebSocket
                # It will be garbage collected
                self.ws = None
                self.connected = False
                self.logger.info("Disconnected from Bybit WebSocket")
                return True
            except Exception as e:
                self.logger.error(f"Error disconnecting from Bybit WebSocket: {str(e)}")
                return False
        return True
        
    def subscribe_orderbook(self, symbol, callback):
        """
        Subscribe to orderbook updates for a symbol
        
        Args:
            symbol: Trading symbol
            callback: Function to call with orderbook updates
        """
        if not self.ws:
            self.logger.error("WebSocket not connected")
            return False
            
        try:
            # Store callback
            self.callbacks[f"orderbook_{symbol}"] = callback
            
            # Define wrapper callback to handle orderbook updates
            def handle_orderbook(message):
                # Call user callback with the message
                callback(message)
            
            # Subscribe to orderbook
            self.ws.orderbook_stream(50, symbol, handle_orderbook)
            
            self.logger.info(f"Subscribed to Bybit orderbook for {symbol}")
            return True
        except Exception as e:
            self.logger.error(f"Error subscribing to Bybit orderbook: {str(e)}")
            return False
            
    def subscribe_trades(self, symbol, callback):
        """
        Subscribe to trade updates for a symbol
        
        Args:
            symbol: Trading symbol
            callback: Function to call with trade updates
        """
        if not self.ws:
            self.logger.error("WebSocket not connected")
            return False
            
        try:
            # Store callback
            self.callbacks[f"trade_{symbol}"] = callback
            
            # Define wrapper callback
            def handle_trade(message):
                # Call user callback with the message
                callback(message)
            
            # Subscribe to trades
            self.ws.trade_stream(symbol, handle_trade)
            
            self.logger.info(f"Subscribed to Bybit trades for {symbol}")
            return True
        except Exception as e:
            self.logger.error(f"Error subscribing to Bybit trades: {str(e)}")
            return False
            
    def _heartbeat_checker(self):
        """Thread to check WebSocket connection health"""
        while self.connected and self.ws:
            time.sleep(5)  # Check every 5 seconds
            
            # Check if too much time has passed since last heartbeat
            if time.time() - self.last_heartbeat > 30:  # 30 seconds
                self.logger.warning("Bybit WebSocket heartbeat timeout. Attempting reconnect.")
                self._reconnect()
                
    def _reconnect(self):
        """Attempt to reconnect WebSocket"""
        if self.reconnect_count >= self.max_reconnect:
            self.logger.error(f"Max reconnect attempts ({self.max_reconnect}) reached for Bybit WebSocket.")
            return False
            
        self.reconnect_count += 1
        self.logger.info(f"Attempting to reconnect Bybit WebSocket (attempt {self.reconnect_count}/{self.max_reconnect})")
        
        try:
            # Disconnect existing connection
            self.disconnect()
            
            # Wait before reconnecting
            time.sleep(1)
            
            # Connect
            success = self.connect()
            
            if success:
                self.logger.info("Successfully reconnected to Bybit WebSocket")
                self.reconnect_count = 0
                
                # Resubscribe to topics
                self._resubscribe()
                
                return True
            else:
                self.logger.error("Failed to reconnect to Bybit WebSocket")
                return False
        except Exception as e:
            self.logger.error(f"Error during Bybit WebSocket reconnect: {str(e)}")
            return False
            
    def _resubscribe(self):
        """Resubscribe to all active topics"""
        for topic, callback in self.callbacks.items():
            try:
                if topic.startswith("orderbook_"):
                    symbol = topic.replace("orderbook_", "")
                    self.subscribe_orderbook(symbol, callback)
                elif topic.startswith("trade_"):
                    symbol = topic.replace("trade_", "")
                    self.subscribe_trades(symbol, callback)
            except Exception as e:
                self.logger.error(f"Error resubscribing to {topic}: {str(e)}")