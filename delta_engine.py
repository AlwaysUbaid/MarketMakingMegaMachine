import logging
import time
from datetime import datetime

class DeltaEngine:
    """Analyzes price differences between exchanges to find arbitrage opportunities"""
    
    def __init__(self, exchange_config):
        self.logger = logging.getLogger(__name__)
        self.config = exchange_config
        self.latest_data = {}  # Store latest normalized data per exchange/symbol
        self.signals = []      # Store recent arbitrage signals
        
    def update_market_data(self, exchange_id, symbol, normalized_data):
        """
        Update latest market data for a symbol/exchange
        
        Args:
            exchange_id: Exchange identifier (e.g., "hyperliquid", "bybit")
            symbol: Symbol in standard base format (e.g., "UBTC/USDC")
            normalized_data: Normalized market data
        """
        if not normalized_data:
            return
            
        # Store by exchange and symbol
        key = f"{exchange_id}_{symbol}"
        self.latest_data[key] = normalized_data
        
    def find_arbitrage_opportunities(self):
        """
        Find arbitrage opportunities across all enabled symbols
        
        Returns:
            List of arbitrage signals
        """
        signals = []
        enabled_symbols = self.config.get_all_enabled_symbols()
        
        for symbol in enabled_symbols:
            # Check if arbitrage is enabled for this symbol
            if not self.config.is_arbitrage_enabled(symbol):
                continue
                
            # Get symbol mappings
            mapping = self.config.get_symbol_mapping(symbol)
            hl_symbol = mapping.get("hyperliquid")
            bybit_symbol = mapping.get("bybit")
            
            # Skip if symbol not available on both exchanges
            if not hl_symbol or not bybit_symbol:
                continue
                
            # Get latest data
            hl_key = f"hyperliquid_{symbol}"
            bybit_key = f"bybit_{symbol}"
            
            hl_data = self.latest_data.get(hl_key)
            bybit_data = self.latest_data.get(bybit_key)
            
            # Skip if we don't have data from both exchanges
            if not hl_data or not bybit_data:
                continue
                
            # Calculate deltas
            signal = self._calculate_delta(symbol, hl_data, bybit_data)
            if signal:
                signals.append(signal)
                
        # Update signals list
        self.signals = signals
        return signals
        
    def _calculate_delta(self, symbol, hl_data, bybit_data):
        """
        Calculate price delta between exchanges and generate signal if threshold exceeded
        
        Args:
            symbol: Base symbol (e.g., "UBTC/USDC")
            hl_data: Normalized Hyperliquid market data
            bybit_data: Normalized Bybit market data
            
        Returns:
            Signal dict if arbitrage opportunity exists, else None
        """
        # Get arbitrage config for this symbol
        arb_config = self.config.get_arbitrage_config(symbol)
        min_delta_percentage = arb_config.get("min_delta_percentage", 0.1)
        max_order_size = arb_config.get("max_order_size", 0.01)
        
        # Extract prices
        hl_bid = hl_data.get("best_bid", 0)
        hl_ask = hl_data.get("best_ask", 0)
        bybit_bid = bybit_data.get("best_bid", 0)
        bybit_ask = bybit_data.get("best_ask", 0)
        
        # Skip if any price is zero
        if not hl_bid or not hl_ask or not bybit_bid or not bybit_ask:
            return None
            
        # Calculate deltas (bid-ask spread across exchanges)
        # Scenario 1: Buy on Bybit, Sell on Hyperliquid
        delta_1 = hl_bid - bybit_ask
        delta_percentage_1 = (delta_1 / bybit_ask) * 100
        
        # Scenario 2: Buy on Hyperliquid, Sell on Bybit
        delta_2 = bybit_bid - hl_ask
        delta_percentage_2 = (delta_2 / hl_ask) * 100
        
        # Check if either delta exceeds threshold
        timestamp = datetime.now().timestamp() * 1000
        
        if delta_percentage_1 >= min_delta_percentage:
            # Arbitrage opportunity: Buy on Bybit, Sell on Hyperliquid
            self.logger.info(f"Arbitrage opportunity: Buy {symbol} on Bybit @ {bybit_ask}, Sell on Hyperliquid @ {hl_bid}, Delta: {delta_percentage_1:.2f}%")
            
            # Calculate optimal order size
            # (In a real system, this would consider available balance, slippage, etc.)
            order_size = min(max_order_size, bybit_data.get("asks", [[0, 0]])[0][1], hl_data.get("bids", [[0, 0]])[0][1])
            
            return {
                "timestamp": timestamp,
                "symbol": symbol,
                "buy_exchange": "bybit",
                "sell_exchange": "hyperliquid",
                "buy_price": bybit_ask,
                "sell_price": hl_bid,
                "delta": delta_1,
                "delta_percentage": delta_percentage_1,
                "order_size": order_size,
                "expected_profit": delta_1 * order_size
            }
            
        elif delta_percentage_2 >= min_delta_percentage:
            # Arbitrage opportunity: Buy on Hyperliquid, Sell on Bybit
            self.logger.info(f"Arbitrage opportunity: Buy {symbol} on Hyperliquid @ {hl_ask}, Sell on Bybit @ {bybit_bid}, Delta: {delta_percentage_2:.2f}%")
            
            # Calculate optimal order size
            order_size = min(max_order_size, hl_data.get("asks", [[0, 0]])[0][1], bybit_data.get("bids", [[0, 0]])[0][1])
            
            return {
                "timestamp": timestamp,
                "symbol": symbol,
                "buy_exchange": "hyperliquid",
                "sell_exchange": "bybit",
                "buy_price": hl_ask,
                "sell_price": bybit_bid,
                "delta": delta_2,
                "delta_percentage": delta_percentage_2,
                "order_size": order_size,
                "expected_profit": delta_2 * order_size
            }
            
        # No arbitrage opportunity
        return None
        
    def get_latest_signals(self, max_age_ms=30000):
        """
        Get recently generated signals that aren't too old
        
        Args:
            max_age_ms: Maximum age of signals in milliseconds (default 30 seconds)
            
        Returns:
            List of recent signals
        """
        current_time = datetime.now().timestamp() * 1000
        recent_signals = [
            signal for signal in self.signals
            if current_time - signal["timestamp"] <= max_age_ms
        ]
        
        return recent_signals