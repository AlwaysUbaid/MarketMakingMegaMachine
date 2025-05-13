import os
import json
import hashlib
import random
import string
import logging
from typing import Dict, Any, Optional

class ConfigManager:
    """Manages configuration settings for Elysium Trading Platform"""
    
    def __init__(self, config_file: str = "elysium_config.json"):
        self.config_file = config_file
        self.config = self.load_config()
        self.logger = logging.getLogger(__name__)
        
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logging.error(f"Error loading config: {str(e)}")
            return {}
    
    def save_config(self) -> bool:
        """Save current configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
            return True
        except Exception as e:
            logging.error(f"Error saving config: {str(e)}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value"""
        return self.config.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set a configuration value"""
        self.config[key] = value
        self.save_config()
    
    def delete(self, key: str) -> None:
        """Delete a configuration value"""
        if key in self.config:
            del self.config[key]
            self.save_config()
    
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
            return self.save_config()
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