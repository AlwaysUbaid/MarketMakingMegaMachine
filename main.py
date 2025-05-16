#!/usr/bin/env python3

import os
import sys
import logging
import argparse
import json
from pathlib import Path
from typing import Dict, Any, Optional

# Import other modules
from api_connector import ApiConnector
from bybit_connector import BybitConnector
from order_handler import OrderHandler
from config_manager import ConfigManager
from terminal_ui import ElysiumTerminalUI
from utils import setup_logging, StatusIcons, Colors


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Market Making Mega Machine (MMMM)')
    parser.add_argument('-c', '--config', type=str, default='mmmm_config.json',
                        help='Path to configuration file')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Enable verbose logging')
    parser.add_argument('-t', '--testnet', action='store_true',
                        help='Use testnet instead of mainnet')
    parser.add_argument('--hyperliquid', action='store_true',
                        help='Connect to Hyperliquid')
    parser.add_argument('--bybit', action='store_true',
                        help='Connect to Bybit')
    parser.add_argument('--auto-connect', action='store_true',
                        help='Automatically connect to exchanges') 
    parser.add_argument('--log-file', type=str, 
                        help='Path to log file')
    parser.add_argument('--strategy', type=str,
                        help='Strategy to start automatically')
    
    return parser.parse_args()


def load_credentials(testnet: bool = False) -> Dict[str, Any]:
    """
    Load credentials from dontshareconfig.py
    
    Args:
        testnet: Whether to load testnet credentials
        
    Returns:
        Dictionary containing credentials
    """
    try:
        import dontshareconfig as ds
        
        creds = {}
        
        # Hyperliquid credentials
        if testnet:
            creds['hl_wallet_address'] = getattr(ds, 'testnet_wallet', None)
            creds['hl_secret_key'] = getattr(ds, 'testnet_secret', None)
        else:
            creds['hl_wallet_address'] = getattr(ds, 'mainnet_wallet', None)
            creds['hl_secret_key'] = getattr(ds, 'mainnet_secret', None)
        
        # Bybit credentials
        if testnet:
            creds['bybit_api_key'] = getattr(ds, 'bybit_testnet_api_key', None)
            creds['bybit_api_secret'] = getattr(ds, 'bybit_testnet_api_secret', None)
        else:
            creds['bybit_api_key'] = getattr(ds, 'bybit_api_key', None)
            creds['bybit_api_secret'] = getattr(ds, 'bybit_api_secret', None)
        
        return creds
    
    except ImportError:
        print("Warning: dontshareconfig.py not found. You will need to enter credentials manually.")
        return {}


def connect_exchanges(args, config_manager, api_connector, bybit_connector, logger):
    """
    Connect to exchanges based on arguments and configuration
    
    Args:
        args: Command line arguments
        config_manager: Configuration manager instance
        api_connector: Hyperliquid API connector instance
        bybit_connector: Bybit connector instance
        logger: Logger instance
        
    Returns:
        Dictionary containing connection statuses
    """
    connection_status = {
        'hyperliquid': False,
        'bybit': False
    }
    
    # Load credentials
    creds = load_credentials(args.testnet)
    
    # Connect to Hyperliquid if specified
    if args.hyperliquid or args.auto_connect or config_manager.get("connect_hl", False):
        if creds.get('hl_wallet_address') and creds.get('hl_secret_key'):
            logger.info(f"Connecting to Hyperliquid {'(testnet)' if args.testnet else '(mainnet)'}")
            try:
                success = api_connector.connect_hyperliquid(
                    creds['hl_wallet_address'], 
                    creds['hl_secret_key'], 
                    args.testnet
                )
                
                if success:
                    logger.info(f"{StatusIcons.SUCCESS} Connected to Hyperliquid: {creds['hl_wallet_address']}")
                    connection_status['hyperliquid'] = True
                else:
                    logger.error(f"{StatusIcons.ERROR} Failed to connect to Hyperliquid")
            except Exception as e:
                logger.error(f"{StatusIcons.ERROR} Error connecting to Hyperliquid: {str(e)}")
        else:
            logger.error(f"{StatusIcons.ERROR} Hyperliquid credentials not found")
    
    # Connect to Bybit if specified
    if args.bybit or args.auto_connect or config_manager.get("connect_bybit", False):
        if creds.get('bybit_api_key') and creds.get('bybit_api_secret'):
            logger.info(f"Connecting to Bybit {'(testnet)' if args.testnet else '(mainnet)'}")
            try:
                success = bybit_connector.connect_bybit(
                    creds['bybit_api_key'], 
                    creds['bybit_api_secret'], 
                    args.testnet
                )
                
                if success:
                    logger.info(f"{StatusIcons.SUCCESS} Connected to Bybit")
                    connection_status['bybit'] = True
                else:
                    logger.error(f"{StatusIcons.ERROR} Failed to connect to Bybit")
            except Exception as e:
                logger.error(f"{StatusIcons.ERROR} Error connecting to Bybit: {str(e)}")
        else:
            logger.error(f"{StatusIcons.ERROR} Bybit credentials not found")
    
    return connection_status


def setup_order_handler(api_connector, bybit_connector, connection_status, logger):
    """
    Set up the order handler with connected exchanges
    
    Args:
        api_connector: Hyperliquid API connector instance
        bybit_connector: Bybit connector instance
        connection_status: Dictionary containing connection statuses
        logger: Logger instance
        
    Returns:
        Configured OrderHandler instance
    """
    # Initialize order handler
    order_handler = OrderHandler(None, None)
    
    # Configure with Hyperliquid if connected
    if connection_status['hyperliquid']:
        order_handler.exchange = api_connector.exchange
        order_handler.info = api_connector.info
        order_handler.wallet_address = api_connector.wallet_address
        order_handler.api_connector = api_connector
        logger.info("Order handler configured with Hyperliquid")
    
    # Configure with Bybit if connected
    if connection_status['bybit']:
        order_handler.set_bybit_connector(bybit_connector)
        logger.info("Order handler configured with Bybit")
    
    # Set the preferred exchange for order execution
    if connection_status['hyperliquid'] and connection_status['bybit']:
        # Default to Hyperliquid if both are connected
        order_handler.set_exchange("hyperliquid")
        logger.info("Order handler default exchange set to hyperliquid")
    elif connection_status['bybit']:
        order_handler.set_exchange("bybit")
        logger.info("Order handler default exchange set to bybit")
    
    return order_handler


def auto_start_strategy(terminal, strategy_name, logger):
    """
    Auto-start a trading strategy if specified
    
    Args:
        terminal: Terminal UI instance
        strategy_name: Name of the strategy to start
        logger: Logger instance
    """
    if not strategy_name:
        return
    
    logger.info(f"Auto-starting strategy: {strategy_name}")
    
    # Check if the strategy exists
    available_strategies = terminal.strategy_selector.list_strategies()
    strategy_exists = any(s['module'] == strategy_name for s in available_strategies)
    
    if not strategy_exists:
        logger.error(f"Strategy '{strategy_name}' not found")
        return
    
    # Start the strategy with default parameters
    success = terminal.strategy_selector.start_strategy(strategy_name)
    
    if success:
        logger.info(f"{StatusIcons.SUCCESS} Started strategy: {strategy_name}")
    else:
        logger.error(f"{StatusIcons.ERROR} Failed to start strategy: {strategy_name}")


def main():
    """Main entry point for the application"""
    # Parse command-line arguments
    args = parse_arguments()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logger = setup_logging(log_level, args.log_file)
    
    # ASCII art header for startup
    ascii_art = '''
    ███╗   ███╗███╗   ███╗███╗   ███╗███╗   ███╗
    ████╗ ████║████╗ ████║████╗ ████║████╗ ████║
    ██╔████╔██║██╔████╔██║██╔████╔██║██╔████╔██║
    ██║╚██╔╝██║██║╚██╔╝██║██║╚██╔╝██║██║╚██╔╝██║
    ██║ ╚═╝ ██║██║ ╚═╝ ██║██║ ╚═╝ ██║██║ ╚═╝ ██║
    ╚═╝     ╚═╝╚═╝     ╚═╝╚═╝     ╚═╝╚═╝     ╚═╝
    ═══════ Market Making Mega Machine ═══════
    ═══════════════════════════════════════════
    '''
    
    logger.info("\n" + ascii_art)
    logger.info("Starting Market Making Mega Machine (MMMM)")
    logger.info(f"Version: 1.1.0 - Cross-Exchange Edition")
    logger.info(f"Mode: {'Testnet' if args.testnet else 'Mainnet'}")
    
    try:
        # Initialize components
        config_manager = ConfigManager(args.config)
        api_connector = ApiConnector()
        bybit_connector = BybitConnector()
        
        # Connect to exchanges
        connection_status = connect_exchanges(
            args, config_manager, api_connector, bybit_connector, logger
        )
        
        # Setup order handler
        order_handler = setup_order_handler(
            api_connector, bybit_connector, connection_status, logger
        )
        
        # Create terminal UI
        terminal = ElysiumTerminalUI(api_connector, order_handler, config_manager)
        
        # Provide bybit connector to terminal UI
        terminal.bybit_connector = bybit_connector
        
        # Update connected exchanges status in terminal
        terminal.connected_exchanges = connection_status
        
        # Set active exchange in terminal
        if connection_status['hyperliquid']:
            terminal.active_exchange = "hyperliquid"
        elif connection_status['bybit']:
            terminal.active_exchange = "bybit"
        
        # Auto-start strategy if specified
        if args.strategy and (connection_status['hyperliquid'] or connection_status['bybit']):
            auto_start_strategy(terminal, args.strategy, logger)
        
        # Start the CLI
        logger.info("Starting Terminal UI")
        terminal.cmdloop()
        
    except KeyboardInterrupt:
        logger.info("Shutting down due to keyboard interrupt")
    except Exception as e:
        logger.error(f"Error in main: {e}", exc_info=True)
    
    logger.info("Market Making Mega Machine shutdown complete")


if __name__ == "__main__":
    main()