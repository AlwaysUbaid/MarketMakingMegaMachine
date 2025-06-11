import os
import json
import hashlib
import random
import string
import logging
from typing import Dict, Any, Optional
from dotenv import load_dotenv

class ConfigManager:
    """Manages configuration and wallet credentials"""
    
    def __init__(self, config_file: str = "config.json"):
        self.logger = logging.getLogger(__name__)
        self.config_file = config_file
        self.config = self._load_config()
        load_dotenv()  # Load environment variables
        
    def _load_config(self) -> dict:
        """Load configuration from file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            self.logger.error(f"Error loading config: {e}")
            return {}
            
    def _save_config(self) -> bool:
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=4)
            return True
        except Exception as e:
            self.logger.error(f"Error saving config: {e}")
            return False
            
    def get_wallet_address(self) -> Optional[str]:
        """Get wallet address from environment or config"""
        # First try environment variable
        wallet_address = os.getenv("WALLET_ADDRESS")
        if wallet_address:
            return wallet_address
            
        # Then try config file
        return self.config.get("wallet_address")
        
    def get_wallet_secret(self) -> Optional[str]:
        """Get wallet secret from environment or config"""
        # First try environment variable
        wallet_secret = os.getenv("WALLET_SECRET")
        if wallet_secret:
            return wallet_secret
            
        # Then try config file
        return self.config.get("wallet_secret")
        
    def set_wallet_credentials(self, address: str, secret: str) -> bool:
        """Set wallet credentials in config"""
        self.config["wallet_address"] = address
        self.config["wallet_secret"] = secret
        return self._save_config()
        
    def get_strategy_config(self, strategy_name: str) -> dict:
        """Get configuration for a specific strategy"""
        return self.config.get("strategies", {}).get(strategy_name, {})
        
    def set_strategy_config(self, strategy_name: str, config: dict) -> bool:
        """Set configuration for a specific strategy"""
        if "strategies" not in self.config:
            self.config["strategies"] = {}
        self.config["strategies"][strategy_name] = config
        return self._save_config()
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value"""
        return self.config.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set a configuration value"""
        self.config[key] = value
        self._save_config()
    
    def delete(self, key: str) -> None:
        """Delete a configuration value"""
        if key in self.config:
            del self.config[key]
            self._save_config()
    
    # Password management methods
    def generate_salt(self) -> str:
        """Generate a random salt for password hashing"""
        return ''.join(random.choices(string.ascii_letters + string.digits, k=16))
    
    def hash_password(self, password: str, salt: str) -> str:
        """Hash a password with the given salt"""
        return hashlib.sha256((password + salt).encode()).hexdigest()
    
    def set_password(self, password: str) -> bool:
        """Set a new password"""
        try:
            salt = self.generate_salt()
            hashed = self.hash_password(password, salt)
            self.config['password_hash'] = hashed
            self.config['salt'] = salt
            return self._save_config()
        except Exception as e:
            self.logger.error(f"Error setting password: {str(e)}")
            return False
    
    def verify_password(self, password: str) -> bool:
        """Verify if the provided password is correct"""
        try:
            if 'password_hash' in self.config and 'salt' in self.config:
                hashed = self.hash_password(password, self.config['salt'])
                return hashed == self.config['password_hash']
            return False
        except Exception as e:
            self.logger.error(f"Error verifying password: {str(e)}")
            return False