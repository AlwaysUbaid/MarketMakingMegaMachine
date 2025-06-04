#!/usr/bin/env python3

import os
import sys
import logging
import argparse
import json
import time
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import other modules
from api_connector import ApiConnector
from order_handler import OrderHandler
from config_manager import ConfigManager
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
    parser.add_argument('-t', '--testnet', action='store_true',
                        help='Use testnet instead of mainnet')
    parser.add_argument('--log-file', type=str, 
                        help='Path to log file')
    parser.add_argument('-s', '--strategy', type=str, required=True,
                        help='Strategy to run (e.g., ubtc_mm, ueth_mm, etc.)')
    parser.add_argument('-p', '--params', type=str,
                        help='JSON string of strategy parameters')
    parser.add_argument('--symbol', type=str,
                        help='Trading pair symbol (e.g., UBTC/USDC)')
    parser.add_argument('--bid-spread', type=float,
                        help='Bid spread as decimal (e.g., 0.0001 for 0.01%)')
    parser.add_argument('--ask-spread', type=float,
                        help='Ask spread as decimal (e.g., 0.0001 for 0.01%)')
    parser.add_argument('--order-amount', type=float,
                        help='Size of each order')
    parser.add_argument('--refresh-time', type=int,
                        help='Time in seconds between order refresh')
    parser.add_argument('--is-perp', action='store_true',
                        help='Trade perpetual contracts instead of spot')
    parser.add_argument('--leverage', type=int, default=1,
                        help='Leverage for perpetual trading')
    parser.add_argument('--use-dynamic-spreads', action='store_true',
                        help='Enable dynamic spread adjustment based on volatility')
    
    return parser.parse_args()

def auto_connect(api_connector, use_testnet=False):
    """Automatically connect to the exchange"""
    logger = logging.getLogger("mmmm")
    
    try:
        # Get credentials from environment variables
        wallet_address = os.getenv('WALLET_ADDRESS')
        secret_key = os.getenv('WALLET_SECRET')
        
        if not wallet_address or not secret_key:
            logger.error("Wallet credentials not found in environment variables")
            return False
        
        network_name = "testnet" if use_testnet else "mainnet"
        logger.info(f"Auto-connecting to Hyperliquid ({network_name})...")
        success = api_connector.connect_hyperliquid(wallet_address, secret_key, use_testnet)
        
        if success:
            logger.info(f"Successfully connected to {wallet_address}")
            return True
        else:
            logger.error("Failed to connect to exchange")
            return False
            
    except Exception as e:
        logger.error(f"Error auto-connecting to exchange: {str(e)}")
        return False

def print_ascii_header():
    """Print the ASCII art header"""
    header = '''
███╗   ███╗███╗   ███╗███╗   ███╗███╗   ███╗
████╗ ████║████╗ ████║████╗ ████║████╗ ████║
██╔████╔██║██╔████╔██║██╔████╔██║██╔████╔██║
██║╚██╔╝██║██║╚██╔╝██║██║╚██╔╝██║██║╚██╔╝██║
██║ ╚═╝ ██║██║ ╚═╝ ██║██║ ╚═╝ ██║██║ ╚═╝ ██║
╚═╝     ╚═╝╚═╝     ╚═╝╚═╝     ╚═╝╚═╝     ╚═╝
═══════ Market Making Mega Machine ═══════
═══════════════════════════════════════════
    '''
    print(header)

def run_headless(api_connector, order_handler, config_manager, strategy_name, strategy_params=None):
    """Run a strategy in headless mode"""
    logger = logging.getLogger("mmmm")
    
    # Initialize strategy selector
    strategy_selector = StrategySelector(api_connector, order_handler, config_manager)
    
    # Parse strategy parameters if provided as a string
    if strategy_params and isinstance(strategy_params, str):
        try:
            strategy_params = json.loads(strategy_params)
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON strategy parameters: {strategy_params}")
            return False
    
    # Start the strategy
    logger.info(f"Starting strategy: {strategy_name}")
    success = strategy_selector.start_strategy(strategy_name, strategy_params)
    
    if success:
        logger.info(f"Strategy {strategy_name} started successfully")
        
        # Keep the main thread alive while the strategy is running
        try:
            while strategy_selector.active_strategy and strategy_selector.active_strategy["instance"].is_running():
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt detected, stopping strategy...")
            strategy_selector.stop_strategy()
            
        return True
    else:
        logger.error(f"Failed to start strategy: {strategy_name}")
        return False

def main():
    """Main entry point for the application"""
    # Parse command-line arguments
    args = parse_arguments()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    setup_logging(log_level, args.log_file)
    
    logger = logging.getLogger("mmmm")
    
    # Display header
    print_ascii_header()
    logger.info("Starting MMMM Trading Platform")
    
    try:
        # Initialize components
        config_manager = ConfigManager(args.config)
        api_connector = ApiConnector()
        order_handler = OrderHandler(None, None)  # Will be initialized when connected
        
        # Set up cross-references between components
        order_handler.api_connector = api_connector
        
        # Automatically connect to the exchange
        if not auto_connect(api_connector, args.testnet):
            logger.error("Failed to auto-connect to exchange. Exiting.")
            sys.exit(1)
        
        # Initialize order handler with the connected exchange and info objects
        order_handler.exchange = api_connector.exchange
        order_handler.info = api_connector.info
        order_handler.wallet_address = api_connector.wallet_address
        
        # Build strategy parameters from command line arguments
        strategy_params = {}
        if args.symbol:
            strategy_params["symbol"] = {"value": args.symbol}
        if args.bid_spread is not None:
            strategy_params["bid_spread"] = {"value": args.bid_spread}
        if args.ask_spread is not None:
            strategy_params["ask_spread"] = {"value": args.ask_spread}
        if args.order_amount is not None:
            strategy_params["order_amount"] = {"value": args.order_amount}
        if args.refresh_time is not None:
            strategy_params["refresh_time"] = {"value": args.refresh_time}
        if args.is_perp:
            strategy_params["is_perp"] = {"value": True}
            if args.leverage > 1:
                strategy_params["leverage"] = {"value": args.leverage}
        if args.use_dynamic_spreads:
            strategy_params["use_dynamic_spreads"] = {"value": True}
        
        # If params were provided as JSON, merge them with command line params
        if args.params:
            try:
                json_params = json.loads(args.params)
                strategy_params.update(json_params)
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON parameters: {args.params}")
                sys.exit(1)
        
        # Run the strategy
        run_headless(api_connector, order_handler, config_manager, args.strategy, strategy_params)
        
    except KeyboardInterrupt:
        logger.info("Shutting down due to keyboard interrupt")
    except Exception as e:
        logger.error(f"Error in main: {e}", exc_info=True)
    
    logger.info("MMMM Trading Platform shutdown complete")

if __name__ == "__main__":
    main()