import numpy as np
import time
from collections import deque
from typing import List, Tuple, Optional

class VolatilitySpreadManager:
    """
    Manages dynamic spread calculation based on market volatility
    """
    
    def __init__(self, base_bid_spread=0.0001, base_ask_spread=0.0001, 
                 volatility_window=300, price_window=100):
        """
        Initialize volatility-based spread manager
        
        Args:
            base_bid_spread: Minimum bid spread (0.01%)
            base_ask_spread: Minimum ask spread (0.01%)
            volatility_window: Time window for volatility calculation (seconds)
            price_window: Number of price points to track
        """
        self.base_bid_spread = base_bid_spread
        self.base_ask_spread = base_ask_spread
        self.volatility_window = volatility_window
        
        # Price tracking for volatility calculation
        self.price_history = deque(maxlen=price_window)
        self.timestamp_history = deque(maxlen=price_window)
        
        # Volatility metrics
        self.current_volatility = 0.0
        self.volatility_percentile = 0.0
        self.volatility_history = deque(maxlen=1000)  # Keep historical volatility
        
        # Spread multipliers based on volatility regime
        self.low_vol_multiplier = 0.8    # Tighter spreads in low vol
        self.medium_vol_multiplier = 1.0  # Base spreads in medium vol
        self.high_vol_multiplier = 2.5   # Wider spreads in high vol
        self.extreme_vol_multiplier = 4.0 # Much wider in extreme vol
        
        # Volume and order book imbalance tracking
        self.recent_volumes = deque(maxlen=50)
        self.bid_ask_imbalances = deque(maxlen=20)
        
    def update_market_data(self, mid_price: float, bid_price: float = None, 
                          ask_price: float = None, volume: float = None, 
                          bid_size: float = None, ask_size: float = None) -> None:
        """
        Update market data for volatility calculation
        
        Args:
            mid_price: Current mid price
            bid_price: Best bid price
            ask_price: Best ask price  
            volume: Recent volume
            bid_size: Total bid size
            ask_size: Total ask size
        """
        current_time = time.time()
        
        # Store price data
        self.price_history.append(mid_price)
        self.timestamp_history.append(current_time)
        
        # Store volume data
        if volume is not None:
            self.recent_volumes.append(volume)
            
        # Store order book imbalance
        if bid_size is not None and ask_size is not None:
            total_size = bid_size + ask_size
            if total_size > 0:
                imbalance = (bid_size - ask_size) / total_size
                self.bid_ask_imbalances.append(imbalance)
        
        # Calculate volatility
        self._calculate_volatility()
        
    def _calculate_volatility(self) -> None:
        """Calculate various volatility measures"""
        if len(self.price_history) < 10:
            return
            
        prices = list(self.price_history)
        timestamps = list(self.timestamp_history)
        current_time = time.time()
        
        # Filter prices within volatility window
        valid_indices = [i for i, ts in enumerate(timestamps) 
                        if current_time - ts <= self.volatility_window]
        
        if len(valid_indices) < 5:
            return
            
        recent_prices = [prices[i] for i in valid_indices]
        recent_timestamps = [timestamps[i] for i in valid_indices]
        
        # Method 1: Returns-based volatility (most common)
        returns = []
        for i in range(1, len(recent_prices)):
            if recent_prices[i-1] > 0:
                ret = (recent_prices[i] - recent_prices[i-1]) / recent_prices[i-1]
                returns.append(ret)
        
        if len(returns) >= 5:
            # Annualized volatility (assuming returns are per-minute intervals)
            std_return = np.std(returns)
            # Convert to annualized volatility (525600 minutes per year)
            time_diff = (recent_timestamps[-1] - recent_timestamps[0]) / 60  # minutes
            periods_per_year = 525600 / max(time_diff / len(returns), 1)
            annualized_vol = std_return * np.sqrt(periods_per_year)
            
            self.current_volatility = annualized_vol
            self.volatility_history.append(annualized_vol)
            
            # Calculate volatility percentile
            if len(self.volatility_history) >= 20:
                sorted_vols = sorted(self.volatility_history)
                percentile_rank = len([v for v in sorted_vols if v <= annualized_vol])
                self.volatility_percentile = percentile_rank / len(sorted_vols)
    
    def get_dynamic_spreads(self, current_spread_bid: float = None, 
                           current_spread_ask: float = None) -> Tuple[float, float]:
        """
        Calculate dynamic spreads based on current market conditions
        
        Args:
            current_spread_bid: Current bid spread (for gradual adjustment)
            current_spread_ask: Current ask spread (for gradual adjustment)
            
        Returns:
            Tuple of (new_bid_spread, new_ask_spread)
        """
        # Start with base spreads  
        new_bid_spread = self.base_bid_spread
        new_ask_spread = self.base_ask_spread
        
        # Volatility-based adjustment
        vol_multiplier = self._get_volatility_multiplier()
        new_bid_spread *= vol_multiplier
        new_ask_spread *= vol_multiplier
        
        # Volume-based adjustment (low volume = wider spreads)
        volume_multiplier = self._get_volume_multiplier()
        new_bid_spread *= volume_multiplier
        new_ask_spread *= volume_multiplier
        
        # Order book imbalance adjustment
        imbalance_bid_adj, imbalance_ask_adj = self._get_imbalance_adjustments()
        new_bid_spread *= imbalance_bid_adj
        new_ask_spread *= imbalance_ask_adj
        
        # Gradual adjustment to prevent sudden spread changes
        if current_spread_bid is not None and current_spread_ask is not None:
            max_change = 0.5  # Maximum 50% change per update
            
            bid_change = (new_bid_spread - current_spread_bid) / current_spread_bid
            ask_change = (new_ask_spread - current_spread_ask) / current_spread_ask
            
            if abs(bid_change) > max_change:
                direction = 1 if bid_change > 0 else -1
                new_bid_spread = current_spread_bid * (1 + direction * max_change)
                
            if abs(ask_change) > max_change:
                direction = 1 if ask_change > 0 else -1
                new_ask_spread = current_spread_ask * (1 + direction * max_change)
        
        # Apply minimum and maximum spread limits
        min_spread = self.base_bid_spread * 0.5  # Never go below 50% of base
        max_spread = self.base_bid_spread * 10.0  # Never go above 1000% of base
        
        new_bid_spread = max(min_spread, min(max_spread, new_bid_spread))
        new_ask_spread = max(min_spread, min(max_spread, new_ask_spread))
        
        return new_bid_spread, new_ask_spread
    
    def _get_volatility_multiplier(self) -> float:
        """Get spread multiplier based on volatility regime"""
        if self.volatility_percentile < 0.2:
            # Low volatility (bottom 20%) - tighten spreads
            return self.low_vol_multiplier
        elif self.volatility_percentile < 0.5:
            # Medium-low volatility  
            return (self.low_vol_multiplier + self.medium_vol_multiplier) / 2
        elif self.volatility_percentile < 0.8:
            # Medium-high volatility
            return self.medium_vol_multiplier
        elif self.volatility_percentile < 0.95:
            # High volatility (80-95th percentile) - widen spreads
            return self.high_vol_multiplier
        else:
            # Extreme volatility (top 5%) - much wider spreads
            return self.extreme_vol_multiplier
    
    def _get_volume_multiplier(self) -> float:
        """Get spread multiplier based on recent volume"""
        if len(self.recent_volumes) < 5:
            return 1.0
            
        recent_avg_volume = np.mean(list(self.recent_volumes)[-10:])
        historical_avg_volume = np.mean(list(self.recent_volumes))
        
        if historical_avg_volume == 0:
            return 1.0
            
        volume_ratio = recent_avg_volume / historical_avg_volume
        
        if volume_ratio > 2.0:
            # High volume - can tighten spreads
            return 0.8
        elif volume_ratio > 1.5:
            return 0.9
        elif volume_ratio < 0.3:
            # Very low volume - widen spreads significantly
            return 1.8
        elif volume_ratio < 0.5:
            # Low volume - widen spreads
            return 1.4
        else:
            return 1.0
    
    def _get_imbalance_adjustments(self) -> Tuple[float, float]:
        """
        Get bid/ask spread adjustments based on order book imbalance
        
        Returns:
            Tuple of (bid_adjustment, ask_adjustment)
        """
        if len(self.bid_ask_imbalances) < 3:
            return 1.0, 1.0
            
        avg_imbalance = np.mean(list(self.bid_ask_imbalances)[-5:])
        
        # Positive imbalance = more bids than asks (bullish pressure)
        # Negative imbalance = more asks than bids (bearish pressure)
        
        if avg_imbalance > 0.3:
            # Strong bid pressure - widen ask spread, tighten bid spread
            return 0.8, 1.4
        elif avg_imbalance > 0.1:
            # Moderate bid pressure
            return 0.9, 1.2
        elif avg_imbalance < -0.3:
            # Strong ask pressure - widen bid spread, tighten ask spread  
            return 1.4, 0.8
        elif avg_imbalance < -0.1:
            # Moderate ask pressure
            return 1.2, 0.9
        else:
            # Balanced order book
            return 1.0, 1.0
    
    def get_diagnostics(self) -> dict:
        """Get current volatility and spread diagnostics"""
        vol_multiplier = self._get_volatility_multiplier()
        volume_multiplier = self._get_volume_multiplier()
        imbalance_bid_adj, imbalance_ask_adj = self._get_imbalance_adjustments()
        
        return {
            "current_volatility": f"{self.current_volatility:.4f}",
            "volatility_percentile": f"{self.volatility_percentile:.2%}",
            "volatility_multiplier": f"{vol_multiplier:.2f}",
            "volume_multiplier": f"{volume_multiplier:.2f}",
            "imbalance_bid_adjustment": f"{imbalance_bid_adj:.2f}",
            "imbalance_ask_adjustment": f"{imbalance_ask_adj:.2f}",
            "price_points_tracked": len(self.price_history),
            "volatility_samples": len(self.volatility_history)
        }

# Example usage of the volatility spread manager
if __name__ == "__main__":
    # This section runs only when this file is executed directly
    print("Volatility Spread Manager - Dynamic Spread Calculator")
    print("\nKey features:")
    print("1. Volatility-based spread adjustment")  
    print("2. Volume-based refinements")
    print("3. Order book imbalance considerations")
    print("4. Gradual spread transitions")
    print("5. Enhanced diagnostics and monitoring")
    
    # Usage example - this doesn't run, just shows how to use the class
    print("\nUsage example:")
    print("manager = VolatilitySpreadManager(base_bid_spread=0.001, base_ask_spread=0.001)")
    print("manager.update_market_data(mid_price=30000, bid_price=29980, ask_price=30020)")
    print("new_bid_spread, new_ask_spread = manager.get_dynamic_spreads()")