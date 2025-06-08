import os
import importlib
import inspect
import logging
import time
from typing import Dict, List, Any, Optional, Callable, Type

# Strategy base class that all strategies should inherit from
class TradingStrategy:
    """Base class for all trading strategies"""
    
    # Class variables for strategy metadata
    STRATEGY_NAME = "Base Strategy"
    STRATEGY_DESCRIPTION = "Base strategy class that all strategies should inherit from"
    STRATEGY_PARAMS = {}  # Default parameters
    
    def __init__(self, api_connector, order_handler, config_manager, params=None):
        """Initialize the strategy with required components"""
        self.api_connector = api_connector
        self.order_handler = order_handler
        self.config_manager = config_manager
        self.params = params or {}
        self.running = False
        self.stop_requested = False
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def start(self):
        """Start the strategy"""
        if not self.running:
            self.running = True
            self.stop_requested = False
            self._run_strategy()
    
    def stop(self):
        """Stop the strategy"""
        self.stop_requested = True
        self.running = False
    
    def is_running(self):
        """Check if strategy is running"""
        return self.running
    
    def _run_strategy(self):
        """Main strategy execution loop - to be implemented by subclasses"""
        raise NotImplementedError("Strategy must implement _run_strategy method")
    
    @classmethod
    def get_strategy_info(cls):
        """Get strategy metadata and parameters"""
        return {
            "name": cls.STRATEGY_NAME,
            "description": cls.STRATEGY_DESCRIPTION,
            "parameters": cls.STRATEGY_PARAMS
        }


class StrategySelector:
    """Handles discovery, configuration and running of trading strategies"""
    
    def __init__(self, api_connector, order_handler, config_manager):
        """
        Initialize the strategy selector
        
        Args:
            api_connector: The API connector to use
            order_handler: The order handler to execute trades
            config_manager: The configuration manager
        """
        self.api_connector = api_connector
        self.order_handler = order_handler
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        self.strategies = {}  # Available strategies
        self.active_strategy = None  # Currently running strategy
        
        # Directory where strategy modules are stored
        self.strategy_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "strategies")
        
        # Create strategies directory if it doesn't exist
        if not os.path.exists(self.strategy_dir):
            os.makedirs(self.strategy_dir)
        
        # Discover available strategies
        self._discover_strategies()
    
    def _discover_strategies(self):
        """
        Discover available strategy modules in the strategies directory
        """
        self.strategies = {}
        
        # Add the strategy directory to sys.path if it's not already there
        import sys
        if self.strategy_dir not in sys.path:
            sys.path.append(self.strategy_dir)
        
        # Look for Python files in the strategy directory
        for filename in os.listdir(self.strategy_dir):
            if filename.endswith(".py") and not filename.startswith("_"):
                module_name = filename[:-3]  # Remove .py extension
                
                try:
                    # Import the module dynamically
                    module = importlib.import_module(module_name)
                    
                    # Find strategy classes in the module
                    for _, obj in inspect.getmembers(module):
                        if (inspect.isclass(obj) and 
                            issubclass(obj, TradingStrategy) and 
                            obj != TradingStrategy):
                            
                            # Add to available strategies
                            self.strategies[module_name] = obj
                            self.logger.info(f"Discovered strategy: {obj.STRATEGY_NAME} from {module_name}")
                
                except Exception as e:
                    self.logger.error(f"Error loading strategy module {module_name}: {str(e)}")
        
        self.logger.info(f"Discovered {len(self.strategies)} trading strategies")
    
    def list_strategies(self):
        """
        List available strategies
        
        Returns:
            List of strategy metadata
        """
        return [
            {
                "module": module_name,
                "name": strategy_class.STRATEGY_NAME,
                "description": strategy_class.STRATEGY_DESCRIPTION
            }
            for module_name, strategy_class in self.strategies.items()
        ]
    
    def get_strategy_params(self, module_name):
        """
        Get parameters for a strategy
        
        Args:
            module_name: Name of the strategy module
            
        Returns:
            Dictionary of parameters
        """
        if module_name not in self.strategies:
            self.logger.error(f"Strategy {module_name} not found")
            return {}
        
        return self.strategies[module_name].STRATEGY_PARAMS.copy()
    
    def start_strategy(self, module_name, params=None):
        """
        Start a trading strategy
        
        Args:
            module_name: Name of the strategy module
            params: Custom parameters for the strategy
            
        Returns:
            True if started successfully, False otherwise
        """
        # Stop any running strategy first
        if self.active_strategy:
            self.stop_strategy()
        
        if module_name not in self.strategies:
            self.logger.error(f"Strategy {module_name} not found")
            return False
        
        # Verify exchange connection is active
        if not self.api_connector.exchange or not self.order_handler.exchange:
            self.logger.error("Exchange connection is not active. Please connect first.")
            return False
            
        try:
            # Ensure the OrderHandler has access to the ApiConnector
            if not self.order_handler.api_connector and hasattr(self.order_handler, 'api_connector'):
                self.order_handler.api_connector = self.api_connector
                self.logger.info("Set api_connector on order_handler")
            
            # Create an instance of the strategy
            self.logger.info(f"Creating instance of {module_name} strategy")
            strategy_class = self.strategies[module_name]
            strategy = strategy_class(
                self.api_connector,
                self.order_handler,
                self.config_manager,
                params
            )
            
            # Log connection info
            self.logger.info(f"Strategy using exchange with wallet: {self.api_connector.wallet_address}")
            
            # Start the strategy in a separate thread
            import threading
            self.logger.info(f"Starting {module_name} strategy in a thread")
            strategy_thread = threading.Thread(target=strategy.start)
            strategy_thread.daemon = True
            strategy_thread.start()
            
            self.active_strategy = {
                "module": module_name,
                "instance": strategy,
                "thread": strategy_thread,
                "params": params
            }
            
            self.logger.info(f"Started strategy: {strategy_class.STRATEGY_NAME}")
            return True
            
        except Exception as e:
            import traceback
            self.logger.error(f"Error starting strategy {module_name}: {str(e)}")
            self.logger.error(traceback.format_exc())
            return False
    
    def stop_strategy(self):
        """
        Stop the currently running strategy
        
        Returns:
            True if stopped successfully, False otherwise
        """
        if not self.active_strategy:
            self.logger.warning("No active strategy to stop")
            return False
        
        try:
            # Stop the strategy
            strategy = self.active_strategy["instance"]
            strategy.stop()
            
            # Wait for the thread to finish
            self.active_strategy["thread"].join(timeout=5)
            
            self.logger.info(f"Stopped strategy: {strategy.STRATEGY_NAME}")
            self.active_strategy = None
            return True
            
        except Exception as e:
            self.logger.error(f"Error stopping strategy: {str(e)}")
            return False
    
    def get_active_strategy(self):
        """
        Get the currently active strategy
        
        Returns:
            Dictionary with active strategy information, or None if no strategy is active
        """
        if not self.active_strategy:
            return None
        
        strategy = self.active_strategy["instance"]
        status_fields = {}
        if hasattr(strategy, "get_status_fields"):
            status_fields = strategy.get_status_fields()
        perf_metrics = {}
        if hasattr(strategy, "get_performance_metrics"):
            perf_metrics = strategy.get_performance_metrics()
        return {
            "module": self.active_strategy["module"],
            "name": strategy.STRATEGY_NAME,
            "running": strategy.is_running(),
            "params": self.active_strategy["params"],
            **status_fields,
            "performance": perf_metrics
        }

    def is_running(self):
        """
        Check if any strategy is currently running
        
        Returns:
            bool: True if a strategy is running, False otherwise
        """
        if not self.active_strategy:
            return False
        return self.active_strategy["instance"].is_running() 