import logging
import sys
import time
from datetime import datetime
import pandas as pd
import numpy as np
from ohlcv_fetcher import OHLCVFetcher
from api_connector import ApiConnector
from order_handler import OrderHandler
from config_manager import ConfigManager

def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)

def calculate_ema(prices: pd.Series, length: int) -> pd.Series:
    """Calculate EMA for given prices"""
    return prices.ewm(span=length, adjust=False).mean()

def get_token_index(symbol: str) -> int:
    """Get token index from token-list.txt"""
    try:
        with open("token-list.txt", "r") as f:
            for line in f:
                if symbol in line:
                    # Extract index from format "@105: HYPE (@107)"
                    index = line.split(":")[0].strip().replace("@", "")
                    return int(index)
        return None
    except Exception as e:
        logging.error(f"Error reading token index: {e}")
        return None

def main():
    """Main entry point for EMA strategy"""
    logger = setup_logging()
    
    try:
        # Initialize components
        api_connector = ApiConnector()
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
            
        # Initialize order handler with both exchange and info objects
        order_handler = OrderHandler(api_connector.exchange, api_connector.info)
        order_handler.api_connector = api_connector  # Set the api_connector reference
        order_handler.wallet_address = wallet_address  # Set the wallet address
        
        # Initialize OHLCV fetcher
        ohlcv_fetcher = OHLCVFetcher(api_connector)
        
        # Get user inputs
        symbol = input("Enter token symbol (e.g., HYPE): ").upper()
        
        # Get token index
        token_index = get_token_index(symbol)
        if token_index is None:
            logger.error(f"Token {symbol} not found in token-list.txt")
            return
            
        logger.info(f"Found token index: {token_index}")
        
        # Ask if user wants to trade perpetuals
        is_perp = input("\nDo you want to trade perpetuals? (y/n): ").lower() == 'y'
        if is_perp:
            symbol = f"{symbol}-PERP"
            try:
                leverage = int(input("\nEnter leverage (1-5): "))
                if leverage < 1 or leverage > 5:
                    raise ValueError("Leverage must be between 1 and 5")
            except ValueError as e:
                logger.error(f"Invalid leverage: {e}")
                return
        
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
        
        logger.info(f"\nStarting EMA strategy for {symbol} (Index: {token_index})")
        logger.info(f"Trading Type: {'Perpetual' if is_perp else 'Spot'}")
        if is_perp:
            logger.info(f"Leverage: {leverage}x")
        logger.info(f"Timeframe: {timeframe}")
        logger.info(f"EMA Length: {ema_length}")
        logger.info(f"Order Size: {order_size}")
        
        # Strategy state
        in_position = False
        position_side = None
        entry_price = 0
        total_profit = 0
        trades_count = 0
        
        while True:
            try:
                # Get OHLCV data using token index
                ohlcv_data = ohlcv_fetcher.get_ohlcv(
                    symbol=f"@{token_index}",  # Use token index with @ prefix
                    timeframe=timeframe,
                    limit=ema_length * 3
                )
                
                if not ohlcv_data:
                    logger.warning("No OHLCV data available")
                    time.sleep(5)
                    continue
                
                # Convert to DataFrame
                df = ohlcv_fetcher.to_dataframe(ohlcv_data)
                
                # Calculate EMA using close prices
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
                        if is_perp:
                            result = order_handler.perp_market_buy(symbol, order_size, leverage, 0.05)
                        else:
                            result = order_handler.market_buy(symbol, order_size, 0.05)
                        if result["status"] == "ok":
                            in_position = True
                            position_side = "long"
                            entry_price = current_price
                            logger.info(f"Entered long position at {entry_price}")
                    elif current_price < current_ema and current_ema < previous_ema:
                        # Sell signal
                        logger.info(f"Sell signal: Price {current_price} crossed below EMA {current_ema}")
                        if is_perp:
                            result = order_handler.perp_market_sell(symbol, order_size, leverage, 0.05)
                        else:
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
                        if is_perp:
                            result = order_handler.perp_market_sell(symbol, order_size, leverage, 0.05)
                        else:
                            result = order_handler.market_sell(symbol, order_size, 0.05)
                        if result["status"] == "ok":
                            profit = (current_price - entry_price) * order_size
                            if is_perp:
                                profit *= leverage
                            total_profit += profit
                            trades_count += 1
                            logger.info(f"Closed long position. Profit: {profit:.2f} USD")
                            logger.info(f"Total Profit: {total_profit:.2f} USD | Trades: {trades_count}")
                            in_position = False
                            position_side = None
                    elif position_side == "short" and current_price >= current_ema:
                        # Close short position
                        logger.info(f"Exit signal: Price {current_price} touched EMA {current_ema}")
                        if is_perp:
                            result = order_handler.perp_market_buy(symbol, order_size, leverage, 0.05)
                        else:
                            result = order_handler.market_buy(symbol, order_size, 0.05)
                        if result["status"] == "ok":
                            profit = (entry_price - current_price) * order_size
                            if is_perp:
                                profit *= leverage
                            total_profit += profit
                            trades_count += 1
                            logger.info(f"Closed short position. Profit: {profit:.2f} USD")
                            logger.info(f"Total Profit: {total_profit:.2f} USD | Trades: {trades_count}")
                            in_position = False
                            position_side = None
                
                # Display current status
                print(f"\rPrice: {current_price:.2f} | EMA: {current_ema:.2f} | Position: {position_side or 'None'} | Total Profit: {total_profit:.2f} USD | Trades: {trades_count}", end='')
                
                time.sleep(5)  # Wait before next iteration
                
            except KeyboardInterrupt:
                logger.info("\nStopping EMA strategy...")
                if in_position:
                    logger.info("Closing open position...")
                    if position_side == "long":
                        if is_perp:
                            order_handler.perp_market_sell(symbol, order_size, leverage, 0.05)
                        else:
                            order_handler.market_sell(symbol, order_size, 0.05)
                    else:
                        if is_perp:
                            order_handler.perp_market_buy(symbol, order_size, leverage, 0.05)
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

if __name__ == "__main__":
    main() 