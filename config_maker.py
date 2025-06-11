import os
import json
from datetime import datetime
from typing import Dict, Any, Optional
import logging

class ConfigMaker:
    """Handles creation and management of strategy configurations"""
    
    def __init__(self, config_dir: str = "configs"):
        self.config_dir = config_dir
        self.logger = logging.getLogger(__name__)
        
        # Create config directory if it doesn't exist
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)
    
    def save_ema_config(self, 
                       timeframe: str,
                       ema_length: int,
                       order_size: float,
                       description: str = "EMA Strategy Configuration") -> bool:
        """
        Save EMA strategy configuration
        
        Args:
            timeframe: Trading timeframe (e.g., "15m", "1h")
            ema_length: Length of EMA calculation
            order_size: Size of orders to place
            description: Optional description of the configuration
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            config = {
                "timeframe": timeframe,
                "ema_length": ema_length,
                "order_size": order_size,
                "description": description,
                "last_updated": datetime.utcnow().isoformat()
            }
            
            # Validate parameters
            if not self._validate_ema_config(config):
                return False
            
            # Save to file
            config_path = os.path.join(self.config_dir, "ema_config.json")
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=4)
            
            self.logger.info(f"Saved EMA configuration to {config_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving EMA configuration: {str(e)}")
            return False
    
    def load_ema_config(self) -> Optional[Dict[str, Any]]:
        """
        Load EMA strategy configuration
        
        Returns:
            Optional[Dict[str, Any]]: Configuration dictionary if successful, None otherwise
        """
        try:
            config_path = os.path.join(self.config_dir, "ema_config.json")
            
            if not os.path.exists(config_path):
                self.logger.warning("No EMA configuration found")
                return None
            
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            # Validate loaded configuration
            if not self._validate_ema_config(config):
                return None
            
            return config
            
        except Exception as e:
            self.logger.error(f"Error loading EMA configuration: {str(e)}")
            return None
    
    def _validate_ema_config(self, config: Dict[str, Any]) -> bool:
        """
        Validate EMA configuration parameters
        
        Args:
            config: Configuration dictionary to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        try:
            # Check required fields
            required_fields = ["timeframe", "ema_length", "order_size"]
            for field in required_fields:
                if field not in config:
                    self.logger.error(f"Missing required field: {field}")
                    return False
            
            # Validate timeframe
            valid_timeframes = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]
            if config["timeframe"] not in valid_timeframes:
                self.logger.error(f"Invalid timeframe: {config['timeframe']}")
                return False
            
            # Validate EMA length
            if not isinstance(config["ema_length"], int) or config["ema_length"] <= 0:
                self.logger.error(f"Invalid EMA length: {config['ema_length']}")
                return False
            
            # Validate order size
            if not isinstance(config["order_size"], (int, float)) or config["order_size"] <= 0:
                self.logger.error(f"Invalid order size: {config['order_size']}")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating EMA configuration: {str(e)}")
            return False
    
    def list_configs(self) -> list:
        """
        List all available configurations
        
        Returns:
            list: List of configuration filenames
        """
        try:
            configs = []
            for file in os.listdir(self.config_dir):
                if file.endswith('.json'):
                    configs.append(file)
            return configs
        except Exception as e:
            self.logger.error(f"Error listing configurations: {str(e)}")
            return []
    
    def get_default_ema_config(self) -> Dict[str, Any]:
        """
        Get default EMA configuration
        
        Returns:
            Dict[str, Any]: Default configuration dictionary
        """
        return {
            "timeframe": "15m",
            "ema_length": 20,
            "order_size": 1.0,
            "description": "Default EMA Strategy Configuration",
            "last_updated": datetime.utcnow().isoformat()
        } 