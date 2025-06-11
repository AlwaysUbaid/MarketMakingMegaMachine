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
    
    def _strategy_loop(self):
        """Main strategy loop"""
        while self.running:
            try:
                # Get OHLCV data
                ohlcv_data = self.ohlcv_fetcher.get_ohlcv(
                    symbol=self.config.symbol,
                    timeframe=self.config.timeframe,
                    limit=self.config.ema_length * 3
                )
                
                if not ohlcv_data:
                    self.logger.warning("No OHLCV data available")
                    time.sleep(5)
                    continue
                
                # Convert to DataFrame
                df = self.ohlcv_fetcher.to_dataframe(ohlcv_data)
                
                # Calculate EMA
                ema = df['close'].ewm(span=self.config.ema_length, adjust=False).mean()
                
                # Get latest values
                current_price = df['close'].iloc[-1]
                current_ema = ema.iloc[-1]
                previous_ema = ema.iloc[-2]
                
                # Generate trading signal
                signal = self._generate_signal(current_price, current_ema, previous_ema)
                
                # Execute trade if signal changed
                if signal != self.last_signal:
                    self._execute_trade(signal)
                    self.last_signal = signal
                
                self.last_update = datetime.now()
                time.sleep(5)  # Wait before next iteration
                
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
                result = self.order_handler.market_buy(
                    self.config.symbol,
                    self.config.order_size,
                    0.05  # 5% slippage
                )
            elif signal == "sell":
                result = self.order_handler.market_sell(
                    self.config.symbol,
                    self.config.order_size,
                    0.05  # 5% slippage
                )
            else:
                return
                
            if result["status"] == "ok":
                self.trades.append({
                    "time": datetime.now(),
                    "signal": signal,
                    "size": self.config.order_size,
                    "symbol": self.config.symbol
                })
                self.logger.info(f"Executed {signal} order for {self.config.symbol}")
            else:
                self.logger.error(f"Failed to execute {signal} order: {result.get('message', 'Unknown error')}")
                
        except Exception as e:
            self.logger.error(f"Error executing trade: {e}")
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Calculate strategy performance metrics"""
        if not self.trades:
            return {
                "total_trades": 0,
                "win_rate": 0,
                "avg_profit": 0
            }
            
        # Calculate metrics
        total_trades = len(self.trades)
        profitable_trades = sum(1 for trade in self.trades if trade.get("profit", 0) > 0)
        total_profit = sum(trade.get("profit", 0) for trade in self.trades)
        
        return {
            "total_trades": total_trades,
            "win_rate": (profitable_trades / total_trades) * 100 if total_trades > 0 else 0,
            "avg_profit": total_profit / total_trades if total_trades > 0 else 0
        } 