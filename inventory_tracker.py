import logging
import time
from datetime import datetime

class InventoryTracker:
    """Tracks and manages balances across exchanges"""
    
    def __init__(self, exchange_config):
        self.logger = logging.getLogger(__name__)
        self.config = exchange_config
        
        # Balance cache
        self.balances = {
            "hyperliquid": {},
            "bybit": {}
        }
        
        # In-flight trades (not yet settled)
        self.in_flight_trades = []
        
        # Last balance update timestamp
        self.last_update = {
            "hyperliquid": 0,
            "bybit": 0
        }
        
    def update_balances(self, exchange_id, balances):
        """
        Update cached balances for an exchange
        
        Args:
            exchange_id: Exchange identifier
            balances: Balance data from exchange
        """
        try:
            if exchange_id not in self.balances:
                self.logger.error(f"Unknown exchange: {exchange_id}")
                return
                
            # Extract and normalize balance data
            normalized_balances = {}
            
            if exchange_id == "hyperliquid":
                # Process Hyperliquid balances
                for balance in balances.get("spot", []):
                    asset = balance.get("asset", "")
                    normalized_balances[asset] = {
                        "total": float(balance.get("total", 0)),
                        "available": float(balance.get("available", 0)),
                        "in_orders": float(balance.get("in_orders", 0))
                    }
                    
            elif exchange_id == "bybit":
                # Process Bybit balances
                for balance in balances.get("spot", []):
                    asset = balance.get("asset", "")
                    normalized_balances[asset] = {
                        "total": float(balance.get("total", 0)),
                        "available": float(balance.get("available", 0)),
                        "in_orders": float(balance.get("in_orders", 0))
                    }
            
            # Update balance cache
            self.balances[exchange_id] = normalized_balances
            self.last_update[exchange_id] = time.time()
            
        except Exception as e:
            self.logger.error(f"Error updating balances for {exchange_id}: {str(e)}")
            
    def add_in_flight_trade(self, trade):
        """
        Add a trade that is in flight (not yet settled)
        
        Args:
            trade: Trade object with exchange, symbol, side, size information
        """
        trade["timestamp"] = time.time()
        self.in_flight_trades.append(trade)
        
        # Update available balance
        self._adjust_available_balance(trade)
        
    def remove_in_flight_trade(self, trade_id):
        """
        Remove an in-flight trade (when settled or cancelled)
        
        Args:
            trade_id: ID of the trade to remove
        """
        for i, trade in enumerate(self.in_flight_trades):
            if trade.get("id") == trade_id:
                self.in_flight_trades.pop(i)
                break
                
    def check_sufficient_balance(self, exchange_id, asset, amount):
        """
        Check if there's sufficient balance for a trade
        
        Args:
            exchange_id: Exchange identifier
            asset: Asset symbol
            amount: Amount needed
            
        Returns:
            bool: True if sufficient balance available
        """
        if exchange_id not in self.balances:
            self.logger.error(f"Unknown exchange: {exchange_id}")
            return False
            
        if asset not in self.balances[exchange_id]:
            self.logger.warning(f"Asset {asset} not found in {exchange_id} balances")
            return False
            
        # Check if available balance is sufficient
        available = self.balances[exchange_id][asset].get("available", 0)
        
        # Account for in-flight trades
        adjusted_available = self._get_adjusted_available(exchange_id, asset, available)
        
        # Check if sufficient
        if adjusted_available >= amount:
            return True
            
        self.logger.warning(f"Insufficient balance on {exchange_id} for {asset}: need {amount}, have {adjusted_available}")
        return False
        
    def get_balance(self, exchange_id, asset):
        """
        Get current balance for an exchange and asset
        
        Args:
            exchange_id: Exchange identifier
            asset: Asset symbol
            
        Returns:
            dict: Balance information or None if not found
        """
        if exchange_id not in self.balances:
            return None
            
        return self.balances[exchange_id].get(asset)
        
    def get_all_balances(self):
        """
        Get all balances across exchanges
        
        Returns:
            dict: All balances by exchange and asset
        """
        return self.balances
        
    def is_balance_fresh(self, exchange_id, max_age_seconds=60):
        """
        Check if balance data is fresh enough
        
        Args:
            exchange_id: Exchange identifier
            max_age_seconds: Maximum age in seconds
            
        Returns:
            bool: True if balance data is fresh
        """
        if exchange_id not in self.last_update:
            return False
            
        age = time.time() - self.last_update[exchange_id]
        return age <= max_age_seconds
        
    def _adjust_available_balance(self, trade):
        """
        Adjust available balance based on a new in-flight trade
        
        Args:
            trade: Trade object
        """
        exchange_id = trade.get("exchange")
        asset = trade.get("asset")
        side = trade.get("side")
        size = trade.get("size")
        
        if not exchange_id or not asset or not side or not size:
            return
            
        if exchange_id not in self.balances or asset not in self.balances[exchange_id]:
            return
            
        # For buy orders, the quote asset (e.g., USDC) is used
        # For sell orders, the base asset (e.g., BTC) is used
        if side == "buy":
            quote_asset = self._get_quote_asset(asset)
            if quote_asset and quote_asset in self.balances[exchange_id]:
                # Calculate approximate cost
                price = trade.get("price", 0)
                cost = size * price
                
                # Reduce available balance
                current = self.balances[exchange_id][quote_asset].get("available", 0)
                self.balances[exchange_id][quote_asset]["available"] = max(0, current - cost)
        else:  # sell
            # Reduce available balance
            current = self.balances[exchange_id][asset].get("available", 0)
            self.balances[exchange_id][asset]["available"] = max(0, current - size)
            
    def _get_adjusted_available(self, exchange_id, asset, available):
        """
        Calculate adjusted available balance accounting for in-flight trades
        
        Args:
            exchange_id: Exchange identifier
            asset: Asset symbol
            available: Current available balance
            
        Returns:
            float: Adjusted available balance
        """
        # Start with current available balance
        adjusted = available
        
        # Adjust for in-flight trades
        for trade in self.in_flight_trades:
            if trade.get("exchange") != exchange_id:
                continue
                
            if trade.get("side") == "buy" and self._get_quote_asset(trade.get("asset")) == asset:
                # This is a buy order using this quote asset
                cost = trade.get("size", 0) * trade.get("price", 0)
                adjusted -= cost
            elif trade.get("side") == "sell" and trade.get("asset") == asset:
                # This is a sell order of this asset
                adjusted -= trade.get("size", 0)
                
        return max(0, adjusted)
        
    def _get_quote_asset(self, symbol):
        """
        Extract quote asset from symbol
        
        Args:
            symbol: Symbol like "UBTC/USDC"
            
        Returns:
            str: Quote asset or None
        """
        if '/' in symbol:
            return symbol.split('/')[1]
        return None