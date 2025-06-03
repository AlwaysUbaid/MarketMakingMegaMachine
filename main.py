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
    parser = argparse.ArgumentParser(description='Elysium Trading Platform')
    parser.add_argument('-c', '--config', type=str, default='elysium_config.json',
                        help='Path to configuration file')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Enable verbose logging')
    parser.add_argument('--log-file', type=str, 
                        help='Path to log file')
    
    return parser.parse_args()


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
    logger.info("Starting Elysium Trading Platform")
    
    try:
        # Initialize components
        config_manager = ConfigManager(args.config)
        api_connector = ApiConnector()
        order_handler = OrderHandler(None, None)  # Will be initialized when connected

        # Set up cross-references between components
        order_handler.api_connector = api_connector  
        
        # Create and start the CLI
        terminal = ElysiumTerminalUI(api_connector, order_handler, config_manager)
        
        # Start the CLI
        terminal.cmdloop()
        
    except KeyboardInterrupt:
        logger.info("Shutting down due to keyboard interrupt")
    except Exception as e:
        logger.error(f"Error in main: {e}", exc_info=True)
    
    logger.info("Elysium Trading Platform shutdown complete")


if __name__ == "__main__":
    main()

    