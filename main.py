#!/usr/bin/env python3

import os
import sys
import logging
import argparse
import json
from pathlib import Path
from dotenv import load_dotenv
import time
from datetime import datetime
import pandas as pd
import numpy as np

# Import other modules
from api_connector import ApiConnector
from order_handler import OrderHandler
from config_manager import ConfigManager
from terminal_ui import ElysiumTerminalUI
from strategy_selector import StrategySelector
from ohlcv_fetcher import OHLCVFetcher


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
    parser.add_argument('-ema', action='store_true', help='Run EMA strategy')
    
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


def calculate_ema(prices: pd.Series, length: int) -> pd.Series:
    """Calculate EMA for given prices"""
    return prices.ewm(span=length, adjust=False).mean()


def run_ema_strategy(args):
    """Run EMA strategy with given parameters"""
    logger = logging.getLogger("elysium")
    
    try:
        # Initialize components
        api_connector = ApiConnector()
        order_handler = OrderHandler(api_connector)
        config_manager = ConfigManager()
        
        # Connect to exchange
        wallet_address = config_manager.get_wallet_address()
        secret_key = config_manager.get_wallet_secret()
        
        if not wallet_address or not secret_key:
            logger.error("Wallet credentials not found. Please set them in config.json")
            return
        
        logger.info("Connecting to Hyperliquid...")
        if not api_connector.connect_hyperliquid(wallet_address, secret_key, False):
            logger.error("Failed to connect to exchange")
            return
        
        # Initialize OHLCV fetcher
        ohlcv_fetcher = OHLCVFetcher(api_connector)
        
        # Get user inputs
        symbol = input("Enter token symbol (e.g., HYPE): ").upper()
        
        print("\nAvailable timeframes:")
        print("1. 1m (1 minute)")
        print("2. 5m (5 minutes)")
        print("3. 15m (15 minutes)")
        print("4. 1h (1 hour)")
        print("5. 4h (4 hours)")
        print("6. 1d (1 day)")
        
        tf_choice = input("\nSelect timeframe (1-6): ")
        timeframe_map = {
            "1": "1m", "2": "5m", "3": "15m",
            "4": "1h", "5": "4h", "6": "1d"
        }
        timeframe = timeframe_map.get(tf_choice)
        
        if not timeframe:
            logger.error("Invalid timeframe selection")
            return
        
        try:
            ema_length = int(input("\nEnter EMA length (e.g., 20): "))
            if ema_length <= 0:
                raise ValueError("EMA length must be positive")
        except ValueError as e:
            logger.error(f"Invalid EMA length: {e}")
            return
        
        try:
            order_size = float(input("\nEnter order size in tokens: "))
            if order_size <= 0:
                raise ValueError("Order size must be positive")
        except ValueError as e:
            logger.error(f"Invalid order size: {e}")
            return
        
        logger.info(f"\nStarting EMA strategy for {symbol}")
        logger.info(f"Timeframe: {timeframe}")
        logger.info(f"EMA Length: {ema_length}")
        logger.info(f"Order Size: {order_size}")
        
        # Strategy state
        in_position = False
        position_side = None
        entry_price = 0
        
        while True:
            try:
                # Get OHLCV data
                ohlcv_data = ohlcv_fetcher.get_ohlcv(
                    symbol=symbol,
                    timeframe=timeframe,
                    limit=ema_length * 3
                )
                
                if not ohlcv_data:
                    logger.warning("No OHLCV data available")
                    time.sleep(5)
                    continue
                
                # Convert to DataFrame
                df = ohlcv_fetcher.to_dataframe(ohlcv_data)
                
                # Calculate EMA
                ema = calculate_ema(df['close'], ema_length)
                
                # Get latest values
                current_price = df['close'].iloc[-1]
                current_ema = ema.iloc[-1]
                previous_ema = ema.iloc[-2]
                
                # Generate trading signal
                if not in_position:
                    if current_price > current_ema and current_ema > previous_ema:
                        # Buy signal
                        logger.info(f"Buy signal: Price {current_price} crossed above EMA {current_ema}")
                        result = order_handler.market_buy(symbol, order_size, 0.05)
                        if result["status"] == "ok":
                            in_position = True
                            position_side = "long"
                            entry_price = current_price
                            logger.info(f"Entered long position at {entry_price}")
                    elif current_price < current_ema and current_ema < previous_ema:
                        # Sell signal
                        logger.info(f"Sell signal: Price {current_price} crossed below EMA {current_ema}")
                        result = order_handler.market_sell(symbol, order_size, 0.05)
                        if result["status"] == "ok":
                            in_position = True
                            position_side = "short"
                            entry_price = current_price
                            logger.info(f"Entered short position at {entry_price}")
                else:
                    # Check for exit conditions
                    if position_side == "long" and current_price <= current_ema:
                        # Close long position
                        logger.info(f"Exit signal: Price {current_price} touched EMA {current_ema}")
                        result = order_handler.market_sell(symbol, order_size, 0.05)
                        if result["status"] == "ok":
                            profit = (current_price - entry_price) * order_size
                            logger.info(f"Closed long position. Profit: {profit:.2f} USD")
                            in_position = False
                            position_side = None
                    elif position_side == "short" and current_price >= current_ema:
                        # Close short position
                        logger.info(f"Exit signal: Price {current_price} touched EMA {current_ema}")
                        result = order_handler.market_buy(symbol, order_size, 0.05)
                        if result["status"] == "ok":
                            profit = (entry_price - current_price) * order_size
                            logger.info(f"Closed short position. Profit: {profit:.2f} USD")
                            in_position = False
                            position_side = None
                
                # Display current status
                print(f"\rPrice: {current_price:.2f} | EMA: {current_ema:.2f} | Position: {position_side or 'None'}", end='')
                
                time.sleep(5)  # Wait before next iteration
                
            except KeyboardInterrupt:
                logger.info("\nStopping EMA strategy...")
                if in_position:
                    logger.info("Closing open position...")
                    if position_side == "long":
                        order_handler.market_sell(symbol, order_size, 0.05)
                    else:
                        order_handler.market_buy(symbol, order_size, 0.05)
                break
            except Exception as e:
                logger.error(f"Error in strategy loop: {e}")
                time.sleep(5)
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        # Cleanup
        if 'ohlcv_fetcher' in locals():
            ohlcv_fetcher.cleanup()


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
        
        # If EMA strategy is specified, run it
        if args.ema:
            run_ema_strategy(args)
        
    except KeyboardInterrupt:
        logger.info("Shutting down due to keyboard interrupt")
    except Exception as e:
        logger.error(f"Error in main: {e}", exc_info=True)
    
    logger.info("MMMM Trading Platform shutdown complete")


if __name__ == "__main__":
    sys.exit(main())

    