#!/usr/bin/env python3

import os
import sys
import logging
import argparse
import json
from pathlib import Path
from dotenv import load_dotenv

# Import other modules
from api_connector import ApiConnector
from order_handler import OrderHandler
from config_manager import ConfigManager
from terminal_ui import ElysiumTerminalUI
from strategy_selector import StrategySelector


def setup_logging(log_level=logging.INFO, log_file=None):
    """Configure logging"""
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter(log_format))
        logging.getLogger().addHandler(file_handler)


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='MMMM Trading Platform')
    parser.add_argument('-c', '--config', type=str, default='elysium_config.json',
                        help='Path to configuration file')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Enable verbose logging')
    parser.add_argument('--log-file', type=str, 
                        help='Path to log file')
    parser.add_argument('-ca', '--cancel-all', action='store_true',
                        help='Emergency cancel all orders and exit')
    parser.add_argument('-t', '--testnet', action='store_true',
                        help='Use testnet instead of mainnet')
    parser.add_argument('-s', '--strategy', type=str,
                        help='Strategy to run (e.g., ubtc_mm, ueth_mm, pure_mm, buddy_mm, usol_mm, ufart_mm)')
    parser.add_argument('--strategy-params', type=str,
                        help='JSON string of strategy parameters')
    
    return parser.parse_args()


def emergency_cancel_all(api_connector, order_handler):
    """Emergency cancel all orders"""
    logger = logging.getLogger("elysium")
    logger.info("Starting emergency order cancellation")
    
    try:
        # Get all open orders
        open_orders = order_handler.get_open_orders()
        if not open_orders:
            logger.info("No open orders found")
            return True
            
        # Cancel all orders
        logger.info(f"Found {len(open_orders)} open orders, cancelling...")
        result = order_handler.cancel_all_orders()
        
        if result.get("status") == "ok":
            logger.info("Successfully cancelled all orders")
            return True
        else:
            logger.error(f"Failed to cancel all orders: {result.get('message', 'Unknown error')}")
            return False
            
    except Exception as e:
        logger.error(f"Error during emergency cancellation: {str(e)}")
        return False


def main():
    """Main entry point for the application"""
    # Load environment variables
    load_dotenv()
    
    # Parse command-line arguments
    args = parse_arguments()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    setup_logging(log_level, args.log_file)
    
    logger = logging.getLogger("elysium")
    logger.info("Starting MMMM Trading Platform")
    
    try:
        # Initialize components
        config_manager = ConfigManager(args.config)
        api_connector = ApiConnector()
        
        # Get credentials from .env
        wallet_address = os.getenv("WALLET_ADDRESS")
        wallet_secret = os.getenv("WALLET_SECRET")
        
        if not wallet_address or not wallet_secret:
            logger.error("Wallet credentials not found in .env file")
            return 1
            
        # Connect to exchange
        if not api_connector.connect_hyperliquid(wallet_address, wallet_secret, args.testnet):
            logger.error("Failed to connect to exchange")
            return 1
            
        # Initialize order handler with exchange connection
        order_handler = OrderHandler(api_connector.exchange, api_connector.info)
        order_handler.api_connector = api_connector  # Set the api_connector reference
        order_handler.wallet_address = wallet_address  # Set the wallet address
        
        strategy_selector = StrategySelector(api_connector, order_handler, config_manager)

        # Handle emergency cancel-all
        if args.cancel_all:
            success = emergency_cancel_all(api_connector, order_handler)
            return 0 if success else 1
        
        # If strategy is specified, run it directly
        if args.strategy:
            # Parse strategy parameters if provided
            strategy_params = None
            if args.strategy_params:
                try:
                    strategy_params = json.loads(args.strategy_params)
                except json.JSONDecodeError:
                    logger.error("Invalid strategy parameters JSON")
                    return 1
            
            # Start the specified strategy
            logger.info(f"Starting strategy: {args.strategy}")
            success = strategy_selector.start_strategy(args.strategy, strategy_params)
            if not success:
                logger.error(f"Failed to start strategy: {args.strategy}")
                return 1
            
            # Keep the main thread alive while strategy runs
            try:
                while strategy_selector.is_running():
                    import time
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("Stopping strategy due to keyboard interrupt")
                strategy_selector.stop_strategy()
            
            return 0
        
        # Create and start the CLI if no strategy specified
        terminal = ElysiumTerminalUI(api_connector, order_handler, config_manager)
        terminal.cmdloop()
        
    except KeyboardInterrupt:
        logger.info("Shutting down due to keyboard interrupt")
    except Exception as e:
        logger.error(f"Error in main: {e}", exc_info=True)
    
    logger.info("MMMM Trading Platform shutdown complete")


if __name__ == "__main__":
    sys.exit(main())

    