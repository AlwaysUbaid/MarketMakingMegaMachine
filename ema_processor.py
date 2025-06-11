import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from ohlcv_fetcher import OHLCVFetcher
from api_connector import ApiConnector

@dataclass
class EMAParams:
    """Parameters for EMA calculation and trading"""
    timeframe: str
    ema_length: int
    symbol: str
    order_size: float  # Added order size parameter

@dataclass
class ProcessedData:
    """Processed OHLCV data with EMA"""
    symbol: str
    timeframe: str
    ohlcv_data: pd.DataFrame
    ema_values: pd.Series
    token_index: int
    last_update: float
    order_size: float  # Added order size to processed data

class EMAProcessor:
    """
    Processes OHLCV data and calculates EMAs
    """
    
    def __init__(self, ohlcv_fetcher: OHLCVFetcher):
        self.ohlcv_fetcher = ohlcv_fetcher
        self.token_indices = self._load_token_indices()
        
    def _load_token_indices(self) -> Dict[str, int]:
        """Load token indices from token-list.txt"""
        token_indices = {}
        try:
            with open('token-list.txt', 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or not line.startswith('@'):
                        continue
                    
                    # Parse line like "@105: HYPE (@107)"
                    try:
                        # Split on first colon
                        index_part, rest = line.split(':', 1)
                        # Get the index number after @
                        index = int(index_part[1:])
                        
                        # Get the token name (everything before the first space after the colon)
                        token = rest.strip().split()[0]
                        
                        token_indices[token] = index
                    except (ValueError, IndexError) as e:
                        print(f"Warning: Could not parse line '{line}': {e}")
                        continue
                        
            print(f"Loaded {len(token_indices)} token indices")
        except Exception as e:
            print(f"Error loading token indices: {e}")
        return token_indices
    
    def get_token_index(self, symbol: str) -> Optional[int]:
        """Get the index for a given token symbol"""
        index = self.token_indices.get(symbol)
        if index is None:
            print(f"Available tokens: {', '.join(sorted(self.token_indices.keys()))}")
        return index
    
    def calculate_ema(self, data: pd.DataFrame, length: int) -> pd.Series:
        """Calculate EMA for the given data"""
        return data['close'].ewm(span=length, adjust=False).mean()
    
    def process_data(self, params: EMAParams) -> Optional[ProcessedData]:
        """
        Process OHLCV data and calculate EMA
        
        Args:
            params: EMAParams object containing timeframe, ema_length, symbol, and order_size
            
        Returns:
            ProcessedData object containing the processed data and EMA values
        """
        try:
            # Get token index
            token_index = self.get_token_index(params.symbol)
            if token_index is None:
                print(f"Token index not found for {params.symbol}")
                return None
            
            # Fetch OHLCV data
            ohlcv_data = self.ohlcv_fetcher.get_ohlcv(
                symbol=params.symbol,
                timeframe=params.timeframe,
                limit=params.ema_length * 3  # Get more data than needed for better EMA calculation
            )
            
            if not ohlcv_data:
                print(f"No OHLCV data available for {params.symbol}")
                return None
            
            # Convert to DataFrame
            df = self.ohlcv_fetcher.to_dataframe(ohlcv_data)
            
            # Calculate EMA
            ema_values = self.calculate_ema(df, params.ema_length)
            
            return ProcessedData(
                symbol=params.symbol,
                timeframe=params.timeframe,
                ohlcv_data=df,
                ema_values=ema_values,
                token_index=token_index,
                last_update=df.index[-1].timestamp(),
                order_size=params.order_size
            )
            
        except Exception as e:
            print(f"Error processing data: {e}")
            return None

def main():
    """Main function to demonstrate usage"""
    # Initialize components
    api_connector = ApiConnector()
    ohlcv_fetcher = OHLCVFetcher(api_connector)
    ema_processor = EMAProcessor(ohlcv_fetcher)
    
    # Get user input
    print("\n=== EMA Trading Strategy Configuration ===")
    symbol = input("Enter token symbol (e.g., BTC): ").upper()
    timeframe = input("Enter timeframe (e.g., 1m, 5m, 15m, 1h): ")
    ema_length = int(input("Enter EMA length: "))
    
    # Get order size with validation
    while True:
        try:
            order_size = float(input("Enter order size in token quantity (e.g., 0.1): "))
            if order_size <= 0:
                print("Order size must be greater than 0")
                continue
            break
        except ValueError:
            print("Please enter a valid number")
    
    # Create parameters
    params = EMAParams(
        timeframe=timeframe,
        ema_length=ema_length,
        symbol=symbol,
        order_size=order_size
    )
    
    # Process data
    result = ema_processor.process_data(params)
    
    if result:
        print(f"\nProcessed data for {result.symbol}:")
        print(f"Token Index: {result.token_index}")
        print(f"Timeframe: {result.timeframe}")
        print(f"Order Size: {result.order_size} {result.symbol}")
        print(f"Last Update: {result.last_update}")
        print("\nLatest OHLCV data:")
        print(result.ohlcv_data.tail())
        print("\nLatest EMA values:")
        print(result.ema_values.tail())
        
        # Calculate potential trade value
        latest_price = result.ohlcv_data['close'].iloc[-1]
        trade_value = result.order_size * latest_price
        print(f"\nEstimated trade value: ${trade_value:.2f} USD")
    else:
        print("Failed to process data")

if __name__ == "__main__":
    main() 