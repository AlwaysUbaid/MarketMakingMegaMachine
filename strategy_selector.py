import os
import importlib
import inspect
import logging
import time
from typing import Dict, List, Any, Optional, Callable, Type
import traceback
import sys

# Specific imports for strategy classes
try:
    from strategies.ubtc_mm import UbtcMarketMaking
except ImportError:
    pass  

try:
    from strategies.ueth_mm import UethMarketMaking
except ImportError:
    pass

try:
    from strategies.ufart_mm import UfartMarketMaking
except ImportError:
    pass

try:
    from strategies.usol_mm import UsolMarketMaking
except ImportError:
    pass

try:
    from strategies.pure_mm import PureMarketMaking
except ImportError:
    pass

# Strategy base class that all strategies should inherit from
class TradingStrategy:
    """Base class for all trading strategies"""
    
    # Class variables for strategy metadata
    STRATEGY_NAME = "Base Strategy"
    STRATEGY_DESCRIPTION = "Base strategy class that all strategies should inherit from"
    STRATEGY_PARAMS = {}  # Default parameters
    
    def __init__(self, api_connector, order_handler, config_manager, params=None):
        """
        Initialize the strategy
        
        Args:
            api_connector: The API connector to use
            order_handler: The order handler to execute trades
            config_manager: The configuration manager
            params: Custom parameters for the strategy
        """
        self.api_connector = api_connector
        self.order_handler = order_handler
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        self.running = False
        self.stop_requested = False
        
        # Merge default params with custom params
        self.params = self.STRATEGY_PARAMS.copy()
        if params:
            self.params.update(params)
    
    def start(self):
        """Start the strategy"""
        self.running = True
        self.stop_requested = False
        self.logger.info(f"Starting {self.STRATEGY_NAME}")
        self._run_strategy()
    
    def stop(self):
        """Stop the strategy"""
        self.logger.info(f"Stopping {self.STRATEGY_NAME}")
        self.stop_requested = True
        self.running = False
    
    def is_running(self):
        """Check if the strategy is running"""
        return self.running
    
    def _run_strategy(self):
        """
        Main strategy logic - to be implemented by subclasses
        This method should include a loop that checks self.stop_requested
        """
        raise NotImplementedError("Subclasses must implement _run_strategy()")
    
    @classmethod
    def get_strategy_info(cls):
        """Get strategy metadata"""
        return {
            "name": cls.STRATEGY_NAME,
            "description": cls.STRATEGY_DESCRIPTION,
            "params": cls.STRATEGY_PARAMS
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
        if self.strategy_dir not in sys.path:
            sys.path.append(self.strategy_dir)
            
        # Add parent directory to sys.path to allow importing strategies as modules
        parent_dir = os.path.dirname(os.path.abspath(__file__))
        if parent_dir not in sys.path:
            sys.path.append(parent_dir)
        
        # Look for Python files in the strategy directory
        for filename in os.listdir(self.strategy_dir):
            if filename.endswith(".py") and not filename.startswith("_"):
                module_name = filename[:-3]  # Remove .py extension
                
                try:
                    # Try importing as a module within the strategies package
                    try:
                        module = importlib.import_module(f"strategies.{module_name}")
                    except ImportError:
                        # Fall back to direct import
                        module = importlib.import_module(module_name)
                    
                    # Find strategy classes in the module
                    for name, obj in inspect.getmembers(module):
                        if (inspect.isclass(obj) and 
                            issubclass(obj, TradingStrategy) and 
                            obj != TradingStrategy):
                            
                            # Add to available strategies
                            self.strategies[module_name] = obj
                            self.logger.info(f"Discovered strategy: {obj.STRATEGY_NAME} from {module_name}")
                
                except Exception as e:
                    self.logger.error(f"Error loading strategy module {module_name}: {str(e)}")
                    self.logger.debug(traceback.format_exc())  # More detailed error
        
        # Manual addition of known strategies
        # This ensures strategies are available even if dynamic discovery fails
        known_strategies = {
            'ubtc_mm': UbtcMarketMaking if 'UbtcMarketMaking' in globals() else None,
            'ueth_mm': UethMarketMaking if 'UethMarketMaking' in globals() else None,
            'ufart_mm': UfartMarketMaking if 'UfartMarketMaking' in globals() else None, 
            'usol_mm': UsolMarketMaking if 'UsolMarketMaking' in globals() else None,
            'pure_mm': PureMarketMaking if 'PureMarketMaking' in globals() else None
        }
        
        for module_name, strategy_class in known_strategies.items():
            if strategy_class and module_name not in self.strategies:
                self.strategies[module_name] = strategy_class
                self.logger.info(f"Manually added strategy: {strategy_class.STRATEGY_NAME} from {module_name}")
        
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
        
        # DIRECT FIX: If module_name is any of our known strategies, directly import if needed
        if module_name == 'ubtc_mm' and module_name not in self.strategies:
            try:
                from strategies.ubtc_mm import UbtcMarketMaking
                self.strategies[module_name] = UbtcMarketMaking
            except ImportError as e:
                self.logger.error(f"Error importing UbtcMarketMaking: {str(e)}")
        elif module_name == 'ueth_mm' and module_name not in self.strategies:
            try:
                from strategies.ueth_mm import UethMarketMaking
                self.strategies[module_name] = UethMarketMaking
            except ImportError as e:
                self.logger.error(f"Error importing UethMarketMaking: {str(e)}")
        elif module_name == 'ufart_mm' and module_name not in self.strategies:
            try:
                from strategies.ufart_mm import UfartMarketMaking
                self.strategies[module_name] = UfartMarketMaking
            except ImportError as e:
                self.logger.error(f"Error importing UfartMarketMaking: {str(e)}")
        elif module_name == 'usol_mm' and module_name not in self.strategies:
            try:
                from strategies.usol_mm import UsolMarketMaking
                self.strategies[module_name] = UsolMarketMaking
            except ImportError as e:
                self.logger.error(f"Error importing UsolMarketMaking: {str(e)}")
        elif module_name == 'pure_mm' and module_name not in self.strategies:
            try:
                from strategies.pure_mm import PureMarketMaking
                self.strategies[module_name] = PureMarketMaking
            except ImportError as e:
                self.logger.error(f"Error importing PureMarketMaking: {str(e)}")
                
        # Check if strategy exists after potential direct imports
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
        return {
            "module": self.active_strategy["module"],
            "name": strategy.STRATEGY_NAME,
            "running": strategy.is_running(),
            "params": self.active_strategy["params"]
        }