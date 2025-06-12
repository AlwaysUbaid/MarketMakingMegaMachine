import logging
import time
from typing import Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import pandas as pd
import numpy as np
from ohlcv_fetcher import OHLCVFetcher

@dataclass
class EMAStrategyConfig:
    """Configuration for EMA strategy"""
    symbol: str
    timeframe: str
    ema_length: int
    order_size: float
    token_index: Optional[int] = None

class EMAStrategy:
    """EMA-based trading strategy"""
    
    def __init__(self, api_connector, order_handler, config_manager):
        self.api_connector = api_connector
        self.order_handler = order_handler
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        
        # Initialize OHLCV fetcher
        self.ohlcv_fetcher = OHLCVFetcher(api_connector)
        
        # Strategy state
        self.running = False
        self.config: Optional[EMAStrategyConfig] = None
        self.last_signal = None
        self.last_update = None
        self.trades = []
        
        # Price and EMA update tracking
        self.last_price_update = 0
        self.last_ema_update = 0
        self.current_price = None
        self.current_ema = None
        self.previous_ema = None
        
        # Position tracking
        self.in_position = False
        self.position_side = None
        self.entry_price = None
        self.position_size = None
        self.total_pnl = 0
        self.total_fees = 0
        self.trades_count = 0
        self.is_perp = False
        self.leverage = 1
        
    def start(self, config: EMAStrategyConfig) -> bool:
        """Start the strategy with given configuration"""
        try:
            if self.running:
                self.logger.warning("Strategy is already running")
                return False
                
            # Validate configuration
            if not self._validate_config(config):
                return False
                
            self.config = config
            self.running = True
            self.last_signal = None
            self.last_update = None
            
            # Start strategy loop in a separate thread
            import threading
            self.strategy_thread = threading.Thread(target=self._strategy_loop)
            self.strategy_thread.daemon = True
            self.strategy_thread.start()
            
            self.logger.info(f"Started EMA strategy for {config.symbol}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error starting strategy: {e}")
            return False
    
    def stop(self) -> bool:
        """Stop the strategy"""
        try:
            if not self.running:
                self.logger.warning("Strategy is not running")
                return False
                
            self.running = False
            if hasattr(self, 'strategy_thread'):
                self.strategy_thread.join(timeout=5)
                
            self.logger.info("Stopped EMA strategy")
            return True
            
        except Exception as e:
            self.logger.error(f"Error stopping strategy: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get current strategy status"""
        if not self.config:
            return {
                "status": "not_configured",
                "message": "Strategy not configured"
            }
            
        return {
            "status": "running" if self.running else "stopped",
            "symbol": self.config.symbol,
            "timeframe": self.config.timeframe,
            "ema_length": self.config.ema_length,
            "order_size": self.config.order_size,
            "last_signal": self.last_signal,
            "last_update": self.last_update,
            "trades": len(self.trades)
        }
    
    def get_config(self) -> Dict[str, Any]:
        """Get strategy configuration"""
        if not self.config:
            return {}
            
        return {
            "symbol": self.config.symbol,
            "timeframe": self.config.timeframe,
            "ema_length": self.config.ema_length,
            "order_size": self.config.order_size,
            "token_index": self.config.token_index
        }
    
    def _validate_config(self, config: EMAStrategyConfig) -> bool:
        """Validate strategy configuration"""
        try:
            # Check required fields
            if not all([config.symbol, config.timeframe, config.ema_length, config.order_size]):
                self.logger.error("Missing required configuration fields")
                return False
                
            # Validate timeframe
            if not self._is_valid_timeframe(config.timeframe):
                self.logger.error(f"Invalid timeframe: {config.timeframe}")
                return False
                
            # Validate order size
            if config.order_size <= 0:
                self.logger.error("Order size must be greater than 0")
                return False
                
            # Validate EMA length
            if config.ema_length <= 0:
                self.logger.error("EMA length must be greater than 0")
                return False
                
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating config: {e}")
            return False
    
    def _is_valid_timeframe(self, timeframe: str) -> bool:
        """Check if timeframe is valid"""
        try:
            unit = timeframe[-1]
            value = int(timeframe[:-1])
            return unit in ['m', 'h', 'd'] and value > 0
        except:
            return False
    
    def _parse_timeframe_to_seconds(self, timeframe: str) -> int:
        """Convert timeframe string to seconds"""
        try:
            unit = timeframe[-1]
            value = int(timeframe[:-1])
            if unit == 'm':
                return value * 60
            elif unit == 'h':
                return value * 3600
            elif unit == 'd':
                return value * 86400
            return 60  # Default to 1 minute
        except:
            return 60
            
    def _should_update_price(self) -> bool:
        """Check if price should be updated (every second)"""
        current_time = time.time()
        return (current_time - self.last_price_update) >= 1
        
    def _should_update_ema(self) -> bool:
        """Check if EMA should be updated (every 1/3 of timeframe)"""
        if not self.config:
            return False
        current_time = time.time()
        timeframe_seconds = self._parse_timeframe_to_seconds(self.config.timeframe)
        ema_interval = timeframe_seconds / 3
        return (current_time - self.last_ema_update) >= ema_interval
        
    def _update_price(self):
        """Update current price"""
        try:
            market_data = self.api_connector.get_market_data(self.config.symbol)
            if market_data and "mid_price" in market_data:
                self.current_price = market_data["mid_price"]
                self.last_price_update = time.time()
        except Exception as e:
            self.logger.error(f"Error updating price: {e}")
            
    def _update_ema(self):
        """Update EMA values"""
        try:
            # Get OHLCV data
            ohlcv_data = self.ohlcv_fetcher.get_ohlcv(
                symbol=self.config.symbol,
                timeframe=self.config.timeframe,
                limit=self.config.ema_length * 3
            )
            
            if not ohlcv_data:
                self.logger.warning("No OHLCV data available")
                return
                
            # Convert to DataFrame
            df = self.ohlcv_fetcher.to_dataframe(ohlcv_data)
            
            # Calculate EMA
            ema = df['close'].ewm(span=self.config.ema_length, adjust=False).mean()
            
            # Update EMA values
            self.previous_ema = self.current_ema
            self.current_ema = ema.iloc[-1]
            self.last_ema_update = time.time()
            
        except Exception as e:
            self.logger.error(f"Error updating EMA: {e}")
            
    def _strategy_loop(self):
        """Main strategy loop"""
        while self.running:
            try:
                # Update price every second
                if self._should_update_price():
                    self._update_price()
                
                # Update EMA at appropriate intervals
                if self._should_update_ema():
                    self._update_ema()
                    
                    # Generate trading signal if we have all required data
                    if all(v is not None for v in [self.current_price, self.current_ema, self.previous_ema]):
                        signal = self._generate_signal(self.current_price, self.current_ema, self.previous_ema)
                        
                        # Execute trade if signal changed
                        if signal != self.last_signal:
                            self._execute_trade(signal)
                            self.last_signal = signal
                            
                        self.last_update = datetime.now()
                
                time.sleep(0.1)  # Small sleep to prevent CPU overuse
                
            except Exception as e:
                self.logger.error(f"Error in strategy loop: {e}")
                time.sleep(5)
    
    def _generate_signal(self, price: float, current_ema: float, previous_ema: float) -> str:
        """Generate trading signal based on EMA crossover"""
        if price > current_ema and current_ema > previous_ema:
            return "buy"
        elif price < current_ema and current_ema < previous_ema:
            return "sell"
        return "neutral"
    
    def _execute_trade(self, signal: str):
        """Execute trade based on signal"""
        try:
            if signal == "buy":
                if self.in_position and self.position_side == "short":
                    # Close short position
                    result = self.order_handler.perp_market_buy(
                        self.config.symbol,
                        self.position_size,
                        self.leverage,
                        0.05  # 5% slippage
                    )
                    if result["status"] == "ok":
                        # Calculate PnL for closing short position
                        # For perpetual contracts, closed PnL = fee + side * (mark_price - entry_price) * position_size
                        side = -1  # Short position
                        pnl = side * (self.current_price - self.entry_price) * self.position_size * self.leverage
                        fee = result.get("fee", 0)
                        self.total_pnl += pnl
                        self.total_fees += fee
                        self.trades_count += 1
                        self.logger.info(f"Closed short position:")
                        self.logger.info(f"  Entry: {self.entry_price:.2f} | Exit: {self.current_price:.2f}")
                        self.logger.info(f"  Size: {self.position_size} | Leverage: {self.leverage}x")
                        self.logger.info(f"  P&L: {pnl:.2f} USD | Fees: {fee:.2f} USD | Net: {(pnl - fee):.2f} USD")
                        self.in_position = False
                        self.position_side = None
                        self.entry_price = None
                        self.position_size = None
                else:
                    # Open long position
                    result = self.order_handler.perp_market_buy(
                        self.config.symbol,
                        self.config.order_size,
                        self.leverage,
                        0.05  # 5% slippage
                    )
                    if result["status"] == "ok":
                        self.in_position = True
                        self.position_side = "long"
                        self.entry_price = self.current_price
                        self.position_size = self.config.order_size
                        self.logger.info(f"Opened long position:")
                        self.logger.info(f"  Entry: {self.entry_price:.2f} | Size: {self.position_size} | Leverage: {self.leverage}x")
                        
            elif signal == "sell":
                if self.in_position and self.position_side == "long":
                    # Close long position
                    result = self.order_handler.perp_market_sell(
                        self.config.symbol,
                        self.position_size,
                        self.leverage,
                        0.05  # 5% slippage
                    )
                    if result["status"] == "ok":
                        # Calculate PnL for closing long position
                        # For perpetual contracts, closed PnL = fee + side * (mark_price - entry_price) * position_size
                        side = 1  # Long position
                        pnl = side * (self.current_price - self.entry_price) * self.position_size * self.leverage
                        fee = result.get("fee", 0)
                        self.total_pnl += pnl
                        self.total_fees += fee
                        self.trades_count += 1
                        self.logger.info(f"Closed long position:")
                        self.logger.info(f"  Entry: {self.entry_price:.2f} | Exit: {self.current_price:.2f}")
                        self.logger.info(f"  Size: {self.position_size} | Leverage: {self.leverage}x")
                        self.logger.info(f"  P&L: {pnl:.2f} USD | Fees: {fee:.2f} USD | Net: {(pnl - fee):.2f} USD")
                        self.in_position = False
                        self.position_side = None
                        self.entry_price = None
                        self.position_size = None
                else:
                    # Open short position
                    result = self.order_handler.perp_market_sell(
                        self.config.symbol,
                        self.config.order_size,
                        self.leverage,
                        0.05  # 5% slippage
                    )
                    if result["status"] == "ok":
                        self.in_position = True
                        self.position_side = "short"
                        self.entry_price = self.current_price
                        self.position_size = self.config.order_size
                        self.logger.info(f"Opened short position:")
                        self.logger.info(f"  Entry: {self.entry_price:.2f} | Size: {self.position_size} | Leverage: {self.leverage}x")
            
            # Log current status with detailed P&L information
            if self.in_position:
                unrealized_pnl = self._calculate_unrealized_pnl()
                self.logger.info(f"Current Position:")
                self.logger.info(f"  Side: {self.position_side.upper()} | Entry: {self.entry_price:.2f} | Current: {self.current_price:.2f}")
                self.logger.info(f"  Size: {self.position_size} | Leverage: {self.leverage}x")
                self.logger.info(f"  Current P&L: {unrealized_pnl:.2f} USD")
            
            # Log total performance metrics
            total_pnl = self.total_pnl + (self._calculate_unrealized_pnl() if self.in_position else 0)
            net_pnl = total_pnl - self.total_fees
            self.logger.info(f"Performance Summary:")
            self.logger.info(f"  Realized P&L: {self.total_pnl:.2f} USD | Fees: {self.total_fees:.2f} USD")
            self.logger.info(f"  Current P&L: {total_pnl:.2f} USD | Net P&L: {net_pnl:.2f} USD")
            self.logger.info(f"  Total Trades: {self.trades_count}")
                
        except Exception as e:
            self.logger.error(f"Error executing trade: {e}")
            
    def _calculate_unrealized_pnl(self) -> float:
        """Calculate unrealized PnL for current position according to Hyperliquid's formula"""
        if not self.in_position or not self.entry_price or not self.current_price:
            return 0.0
        
        # For perpetual contracts, unrealized PnL = side * (mark_price - entry_price) * position_size
        # where side = 1 for long positions and -1 for short positions
        side = 1 if self.position_side == "long" else -1
        return side * (self.current_price - self.entry_price) * self.position_size * self.leverage
            
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Calculate strategy performance metrics"""
        try:
            # Calculate unrealized PnL for current position
            unrealized_pnl = self._calculate_unrealized_pnl()
            
            # Get current position info
            position_info = None
            if self.in_position:
                position_info = {
                    "side": self.position_side,
                    "entry_price": self.entry_price,
                    "size": self.position_size,
                    "leverage": self.leverage,
                    "unrealized_pnl": unrealized_pnl
                }
            
            # Calculate total P&L (realized + unrealized)
            total_pnl = self.total_pnl + unrealized_pnl
            net_pnl = total_pnl - self.total_fees
            
            # Log real-time P&L
            self.logger.info(f"P&L Update - Realized: {self.total_pnl:.2f} USD | Unrealized: {unrealized_pnl:.2f} USD | Total: {total_pnl:.2f} USD | Net: {net_pnl:.2f} USD")
            
            return {
                "total_trades": self.trades_count,
                "total_realized_pnl": self.total_pnl,
                "total_fees": self.total_fees,
                "net_realized_pnl": self.total_pnl - self.total_fees,
                "current_position": position_info,
                "total_pnl": total_pnl,  # Total PnL including unrealized
                "net_pnl": net_pnl  # Net PnL including unrealized
            }
        except Exception as e:
            self.logger.error(f"Error calculating performance metrics: {e}")
            return {
                "error": str(e)
            } 