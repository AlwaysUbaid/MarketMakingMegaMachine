import logging
import time
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from dataclasses import dataclass
from collections import deque
import threading
from concurrent.futures import ThreadPoolExecutor
import math
import statistics

@dataclass
class OHLCV:
    """OHLCV data structure"""
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OHLCV':
        return cls(
            timestamp=int(data["timestamp"]),
            open=float(data["open"]),
            high=float(data["high"]),
            low=float(data["low"]),
            close=float(data["close"]),
            volume=float(data["volume"])
        )

class OHLCVFetcher:
    """
    Efficient OHLCV data fetcher for HyperLiquid with caching and real-time updates
    """
    
    def __init__(self, api_connector, max_cache_size: int = 1000):
        """
        Initialize the OHLCV fetcher
        
        Args:
            api_connector: HyperLiquid API connector instance
            max_cache_size: Maximum number of candles to cache per symbol
        """
        self.api_connector = api_connector
        self.logger = logging.getLogger(__name__)
        self.max_cache_size = max_cache_size
        
        # Cache for OHLCV data
        self.cache: Dict[str, deque] = {}
        self.cache_lock = threading.Lock()
        
        # Real-time update tracking
        self.last_update: Dict[str, float] = {}
        self.update_interval = 1.0  # seconds
        
        # Thread pool for concurrent fetching
        self.executor = ThreadPoolExecutor(max_workers=5)
        
        # Start background update thread
        self.running = True
        self.update_thread = threading.Thread(target=self._update_loop)
        self.update_thread.daemon = True
        self.update_thread.start()
    
    def _update_loop(self):
        """Background thread for real-time updates"""
        while self.running:
            try:
                self._update_all_cached()
                time.sleep(self.update_interval)
            except Exception as e:
                self.logger.error(f"Error in update loop: {str(e)}")
                time.sleep(5)  # Back off on error
    
    def _update_all_cached(self):
        """Update all cached symbols"""
        with self.cache_lock:
            symbols = list(self.cache.keys())
        
        for symbol in symbols:
            try:
                self._update_symbol(symbol)
            except Exception as e:
                self.logger.error(f"Error updating {symbol}: {str(e)}")
    
    def _update_symbol(self, symbol: str):
        """Update OHLCV data for a specific symbol"""
        try:
            # Get latest market data
            market_data = self.api_connector.get_market_data(symbol)
            if not market_data or "error" in market_data:
                return
            
            current_price = market_data.get("mid_price")
            if not current_price:
                return
            
            current_time = int(time.time() * 1000)  # milliseconds
            
            with self.cache_lock:
                if symbol not in self.cache:
                    return
                
                candles = self.cache[symbol]
                if not candles:
                    return
                
                # Update the latest candle
                latest = candles[-1]
                latest.high = max(latest.high, current_price)
                latest.low = min(latest.low, current_price)
                latest.close = current_price
                latest.volume += market_data.get("volume", 0)
                
                self.last_update[symbol] = time.time()
                
        except Exception as e:
            self.logger.error(f"Error updating {symbol}: {str(e)}")
    
    def get_ohlcv(self, symbol: str, timeframe: str, limit: int,
                  start_time: Optional[int] = None, end_time: Optional[int] = None) -> List[OHLCV]:
        """
        Get OHLCV data for a symbol
        
        Args:
            symbol: Trading pair symbol
            timeframe: Candle timeframe (e.g., "1m", "5m", "15m", "1h", "4h", "1d")
            limit: Maximum number of candles to return
            start_time: Start time in milliseconds (optional)
            end_time: End time in milliseconds (optional)
            
        Returns:
            List of OHLCV objects
        """
        try:
            # Parse timeframe
            interval = self._parse_timeframe(timeframe)
            if not interval:
                raise ValueError(f"Invalid timeframe: {timeframe}")
            
            # Check cache first
            with self.cache_lock:
                if symbol in self.cache:
                    cached_data = list(self.cache[symbol])
                    if self._is_cache_valid(symbol, interval):
                        return self._filter_cached_data(cached_data, start_time, end_time, limit)
            
            # Fetch new data if cache miss or invalid
            return self._fetch_ohlcv(symbol, interval, limit, start_time, end_time)
            
        except Exception as e:
            self.logger.error(f"Error getting OHLCV data: {str(e)}")
            return []
    
    def _parse_timeframe(self, timeframe: str) -> Optional[int]:
        """Parse timeframe string to milliseconds"""
        try:
            unit = timeframe[-1]
            value = int(timeframe[:-1])
            
            if unit == 'm':
                return value * 60 * 1000
            elif unit == 'h':
                return value * 60 * 60 * 1000
            elif unit == 'd':
                return value * 24 * 60 * 60 * 1000
            else:
                return None
        except:
            return None
    
    def _is_cache_valid(self, symbol: str, interval: int) -> bool:
        """Check if cached data is still valid"""
        if symbol not in self.last_update:
            return False
        
        last_update = self.last_update[symbol]
        return (time.time() - last_update) < (interval / 1000)
    
    def _filter_cached_data(self, data: List[OHLCV], 
                           start_time: Optional[int],
                           end_time: Optional[int],
                           limit: int) -> List[OHLCV]:
        """Filter cached data based on time range and limit"""
        filtered = data
        
        if start_time:
            filtered = [c for c in filtered if c.timestamp >= start_time]
        if end_time:
            filtered = [c for c in filtered if c.timestamp <= end_time]
            
        return filtered[-limit:]
    
    def _fetch_ohlcv(self, symbol: str, interval: int, limit: int,
                     start_time: Optional[int], end_time: Optional[int]) -> List[OHLCV]:
        """Fetch OHLCV data from HyperLiquid"""
        try:
            # Convert interval from milliseconds to string format
            interval_str = self._format_interval(interval)
            
            # Format symbol correctly (remove -PERP if present)
            formatted_symbol = symbol.replace("-PERP", "")
            
            # Calculate time range if not provided
            if not end_time:
                end_time = int(time.time() * 1000)
            if not start_time:
                # Calculate start time based on interval and limit
                start_time = end_time - (interval * limit)
            
            # Fetch candles from API
            candles_data = self.api_connector.get_candles(
                symbol=formatted_symbol,
                interval=interval_str,
                start_time=start_time,
                end_time=end_time
            )
            
            if not candles_data:
                self.logger.error(f"No candles returned for {symbol}")
                return []
            
            # Convert to OHLCV objects
            candles = []
            for candle in candles_data:
                candles.append(OHLCV(
                    timestamp=candle["timestamp"],
                    open=candle["open"],
                    high=candle["high"],
                    low=candle["low"],
                    close=candle["close"],
                    volume=candle["volume"]
                ))
            
            # Update cache
            with self.cache_lock:
                self.cache[symbol] = deque(candles, maxlen=self.max_cache_size)
                self.last_update[symbol] = time.time()
            
            return candles
            
        except Exception as e:
            self.logger.error(f"Error fetching OHLCV data: {str(e)}")
            return []
            
    def _format_interval(self, interval_ms: int) -> str:
        """Convert interval in milliseconds to string format"""
        if interval_ms < 60000:  # Less than 1 minute
            return f"{interval_ms // 1000}s"
        elif interval_ms < 3600000:  # Less than 1 hour
            return f"{interval_ms // 60000}m"
        elif interval_ms < 86400000:  # Less than 1 day
            return f"{interval_ms // 3600000}h"
        else:
            return f"{interval_ms // 86400000}d"
    
    def _calculate_mark_price(self, market_data: Dict) -> float:
        """Calculate mark price according to HyperLiquid's specification"""
        try:
            # Get the three components of mark price
            oracle_price = market_data.get("oracle_price", 0)
            mid_price = market_data.get("mid_price", 0)
            last_trade = market_data.get("last_trade_price", 0)
            
            # Get best bid and ask
            order_book = market_data.get("order_book", {})
            best_bid = float(order_book.get("levels", [[{"px": 0}]])[0][0].get("px", 0))
            best_ask = float(order_book.get("levels", [[], [{"px": 0}]])[1][0].get("px", 0))
            
            # Calculate component 1: Oracle price + 150s EMA of mid-oracle difference
            if not hasattr(self, '_ema_numerator'):
                self._ema_numerator = 0
                self._ema_denominator = 0
                self._last_ema_update = time.time()
            
            current_time = time.time()
            t = current_time - self._last_ema_update
            
            # Update EMA
            sample = mid_price - oracle_price
            self._ema_numerator = self._ema_numerator * math.exp(-t / 150) + sample * t
            self._ema_denominator = self._ema_denominator * math.exp(-t / 150) + t
            self._last_ema_update = current_time
            
            ema_diff = self._ema_numerator / self._ema_denominator if self._ema_denominator > 0 else 0
            component1 = oracle_price + ema_diff
            
            # Calculate component 2: Median of best bid, best ask, last trade
            component2 = statistics.median([best_bid, best_ask, last_trade])
            
            # Calculate component 3: Weighted median of CEX prices
            # Note: This would require additional API calls to CEXes
            # For now, we'll use component2 as a fallback
            component3 = component2
            
            # Calculate final mark price as median of components
            mark_price = statistics.median([component1, component2, component3])
            
            return mark_price
            
        except Exception as e:
            self.logger.error(f"Error calculating mark price: {str(e)}")
            return 0

    def _process_order_book(self, order_book: Dict, interval: int, limit: int) -> List[OHLCV]:
        """Process order book data into OHLCV candles using HyperLiquid's mark price"""
        try:
            candles = []
            current_time = int(time.time() * 1000)
            
            # Validate order book structure
            if not isinstance(order_book, dict) or "levels" not in order_book:
                self.logger.error("Invalid order book structure")
                return []
            
            # Get market data for mark price calculation
            market_data = self.api_connector.get_market_data(self.current_symbol)
            if not market_data:
                self.logger.error("Failed to get market data")
                return []
            
            # Calculate mark price
            mark_price = self._calculate_mark_price(market_data)
            if mark_price <= 0:
                self.logger.error("Invalid mark price calculated")
                return []
            
            # Create candles using mark price
            for i in range(limit):
                try:
                    # Align candle time to interval
                    candle_time = (current_time // interval) * interval - (i * interval)
                    
                    # For now, use mark price for all OHLC values
                    # In a real implementation, you would track price changes over time
                    candle = OHLCV(
                        timestamp=candle_time,
                        open=mark_price,
                        high=mark_price,
                        low=mark_price,
                        close=mark_price,
                        volume=0  # Volume would need to be tracked separately
                    )
                    candles.append(candle)
                except Exception as e:
                    self.logger.warning(f"Error creating candle: {str(e)}")
                    continue
            
            return candles
            
        except Exception as e:
            self.logger.error(f"Error processing order book: {str(e)}")
            return []
    
    def get_latest_candle(self, symbol: str, timeframe: str = "1m") -> Optional[OHLCV]:
        """Get the latest candle for a symbol"""
        candles = self.get_ohlcv(symbol, timeframe, limit=1)
        return candles[0] if candles else None
    
    def get_historical_ohlcv(self, symbol: str, start_time: int, end_time: int, timeframe: str = "1m") -> List[OHLCV]:
        """Get historical OHLCV data for a specific time range"""
        return self.get_ohlcv(symbol, timeframe, limit=1000,
                             start_time=start_time, end_time=end_time)
    
    def to_dataframe(self, ohlcv_data: List[OHLCV]) -> pd.DataFrame:
        """Convert OHLCV data to pandas DataFrame"""
        if not ohlcv_data:
            return pd.DataFrame()
            
        data = [candle.to_dict() for candle in ohlcv_data]
        df = pd.DataFrame(data)
        df.set_index('timestamp', inplace=True)
        df.index = pd.to_datetime(df.index, unit='ms')
        return df
    
    def calculate_indicators(self, ohlcv_data: List[OHLCV]) -> Dict[str, List[float]]:
        """Calculate common technical indicators from OHLCV data"""
        if not ohlcv_data:
            return {}
            
        df = self.to_dataframe(ohlcv_data)
        
        # Calculate indicators
        indicators = {
            "sma_20": df["close"].rolling(window=20).mean().tolist(),
            "sma_50": df["close"].rolling(window=50).mean().tolist(),
            "rsi_14": self._calculate_rsi(df["close"]).tolist(),
            "atr_14": self._calculate_atr(df).tolist()
        }
        
        return indicators
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI indicator"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate ATR indicator"""
        high = df["high"]
        low = df["low"]
        close = df["close"]
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()
    
    def cleanup(self):
        """Clean up resources"""
        self.running = False
        if self.update_thread.is_alive():
            self.update_thread.join(timeout=5)
        self.executor.shutdown(wait=True)
    
    def __del__(self):
        """Destructor"""
        self.cleanup() 