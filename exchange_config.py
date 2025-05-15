import os
import json
import logging

class ExchangeConfig:
    """Manages configuration for cross-exchange operations"""
    
    def __init__(self, config_file="exchange_config.json"):
        self.logger = logging.getLogger(__name__)
        self.config_file = config_file
        self.config = self._load_config()
        
    def _load_config(self):
        """Load configuration from file or create default"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            else:
                # Create default config
                default_config = {
                    "symbol_mapping": {
                        "UBTC/USDC": {
                            "hyperliquid": "UBTC/USDC",
                            "bybit": "BTCUSDT"
                        },
                        "UETH/USDC": {
                            "hyperliquid": "UETH/USDC",
                            "bybit": "ETHUSDT"
                        },
                        "USOL/USDC": {
                            "hyperliquid": "USOL/USDC",
                            "bybit": "SOLUSDT"
                        },
                        "UFART/USDC": {
                            "hyperliquid": "UFART/USDC",
                            "bybit": None  # Not available on Bybit
                        }
                    },
                    "arbitrage_config": {
                        "UBTC/USDC": {
                            "enabled": True,
                            "min_delta_percentage": 0.1,
                            "max_order_size": 0.01,
                            "max_inventory_imbalance": 0.03
                        },
                        "UETH/USDC": {
                            "enabled": True,
                            "min_delta_percentage": 0.15,
                            "max_order_size": 0.1,
                            "max_inventory_imbalance": 0.5
                        },
                        "USOL/USDC": {
                            "enabled": True,
                            "min_delta_percentage": 0.2,
                            "max_order_size": 0.5,
                            "max_inventory_imbalance": 1.0
                        },
                        "UFART/USDC": {
                            "enabled": False
                        }
                    },
                    "exchanges": {
                        "hyperliquid": {
                            "enabled": True
                        },
                        "bybit": {
                            "enabled": True,
                            "testnet": True,
                            "api_key": "",
                            "api_secret": ""
                        }
                    }
                }
                
                # Save default config
                with open(self.config_file, 'w') as f:
                    json.dump(default_config, f, indent=2)
                    
                return default_config
                
        except Exception as e:
            self.logger.error(f"Error loading config: {str(e)}")
            return {}
            
    def save_config(self):
        """Save current configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
            return True
        except Exception as e:
            self.logger.error(f"Error saving config: {str(e)}")
            return False
            
    def get_symbol_mapping(self, base_symbol):
        """Get symbol mapping for all exchanges"""
        return self.config.get("symbol_mapping", {}).get(base_symbol, {})
        
    def get_bybit_symbol(self, hl_symbol):
        """Get Bybit symbol corresponding to Hyperliquid symbol"""
        for base_symbol, mapping in self.config.get("symbol_mapping", {}).items():
            if mapping.get("hyperliquid") == hl_symbol:
                return mapping.get("bybit")
        return None
        
    def get_arbitrage_config(self, base_symbol):
        """Get arbitrage configuration for a symbol"""
        return self.config.get("arbitrage_config", {}).get(base_symbol, {})
        
    def is_arbitrage_enabled(self, base_symbol):
        """Check if arbitrage is enabled for a symbol"""
        arb_config = self.get_arbitrage_config(base_symbol)
        return arb_config.get("enabled", False)
        
    def get_exchange_config(self, exchange_name):
        """Get configuration for a specific exchange"""
        return self.config.get("exchanges", {}).get(exchange_name, {})
        
    def is_exchange_enabled(self, exchange_name):
        """Check if an exchange is enabled"""
        exchange_config = self.get_exchange_config(exchange_name)
        return exchange_config.get("enabled", False)
        
    def get_all_enabled_symbols(self):
        """Get all symbols that have arbitrage enabled"""
        enabled_symbols = []
        for symbol, config in self.config.get("arbitrage_config", {}).items():
            if config.get("enabled", False):
                enabled_symbols.append(symbol)
        return enabled_symbols