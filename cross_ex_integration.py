import logging
import time
import importlib
import sys
import os

def setup_logging():
    """Set up logging for the cross-exchange integration"""
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("cross_ex_arb.log")
        ]
    )

def init_modules():
    """Initialize all required modules and ensure they are available"""
    required_modules = [
        "pybit",
        "requests",
        "websocket-client"
    ]
    
    missing_modules = []
    
    for module in required_modules:
        try:
            importlib.import_module(module)
        except ImportError:
            missing_modules.append(module)
    
    if missing_modules:
        print(f"Missing required modules: {', '.join(missing_modules)}")
        print("Please install them using:")
        print(f"pip install {' '.join(missing_modules)}")
        return False
    
    return True

def check_credentials():
    """Check if necessary credentials are available"""
    try:
        import dontshareconfig as ds
        
        # Check for Hyperliquid credentials
        if not hasattr(ds, 'mainnet_wallet') or not hasattr(ds, 'mainnet_secret'):
            print("Hyperliquid credentials not found in dontshareconfig.py")
            return False
        
        # Check for Bybit credentials
        if not hasattr(ds, 'bybit_mainnet_api_key') or not hasattr(ds, 'bybit_mainnet_api_secret'):
            print("Bybit credentials not found in dontshareconfig.py")
            print("Please add the following to dontshareconfig.py:")
            print("bybit_testnet_api_key = 'your_testnet_api_key'")
            print("bybit_testnet_api_secret = 'your_testnet_api_secret'")
            print("bybit_mainnet_api_key = 'your_mainnet_api_key'")
            print("bybit_mainnet_api_secret = 'your_mainnet_api_secret'")
            return False
        
        return True
    except ImportError:
        print("dontshareconfig.py not found")
        print("Please create this file with your exchange credentials")
        return False

def integrate():
    """Main integration function"""
    print("Integrating Cross-Exchange Arbitrage functionality...")
    
    # Set up logging
    setup_logging()
    logger = logging.getLogger("cross_ex_integration")
    
    # Initialize modules
    if not init_modules():
        return False
    
    # Check credentials
    if not check_credentials():
        return False
    
    # Create required directories
    os.makedirs("logs", exist_ok=True)
    
    # Create exchange config if it doesn't exist
    try:
        from exchange_config import ExchangeConfig
        config = ExchangeConfig()
        logger.info("Exchange configuration initialized")
    except Exception as e:
        logger.error(f"Error initializing exchange configuration: {str(e)}")
        return False
    
    logger.info("Cross-Exchange Arbitrage functionality integrated successfully")
    print("Integration complete! Use the terminal UI to access new cross-exchange commands.")
    
    return True

def main():
    """Entry point for the cross-exchange integration"""
    success = integrate()
    
    if success:
        # Optionally, can import and start the terminal UI directly
        # from terminal_ui import ElysiumTerminalUI
        # terminal = ElysiumTerminalUI(...)
        # terminal.cmdloop()
        pass
    else:
        print("Integration failed. Please check the logs for more information.")

if __name__ == "__main__":
    main()