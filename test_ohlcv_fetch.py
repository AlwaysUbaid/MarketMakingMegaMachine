import time
import requests
from datetime import datetime, timedelta
import pandas as pd
import json

def fetch_ohlcv_data():
    # Calculate time range (last 7 days)
    end_time = int(time.time() * 1000)  # Current time in milliseconds
    start_time = end_time - (7 * 24 * 60 * 60 * 1000)  # 7 days ago in milliseconds
    
    # API endpoint
    url = "https://api.hyperliquid.xyz/info"
    
    # Request headers
    headers = {
        "Content-Type": "application/json"
    }
    
    # Request body
    payload = {
        "type": "candleSnapshot",
        "req": {
            "coin": "@107",  # Using @107 as specified
            "interval": "1h",  # 1 hour candles
            "startTime": start_time,
            "endTime": end_time
        }
    }
    
    try:
        # Make the API request
        response = requests.post(url, json=payload, headers=headers)
        
        # Check if request was successful
        if response.status_code == 200:
            data = response.json()
            
            # Print raw response to understand structure
            print("\nRaw API Response:")
            print(json.dumps(data[0] if data else {}, indent=2))
            
            # Convert to pandas DataFrame
            df = pd.DataFrame(data)
            
            # Print DataFrame info
            print("\nDataFrame Info:")
            print(df.info())
            
            # Print column names
            print("\nColumn Names:")
            print(df.columns.tolist())
            
            # Print first row
            print("\nFirst Row:")
            print(df.iloc[0] if not df.empty else "No data")
            
            return df
            
        else:
            print(f"Error: {response.status_code}")
            print(response.text)
            return None
            
    except Exception as e:
        print(f"Error fetching data: {str(e)}")
        return None

if __name__ == "__main__":
    print("Fetching OHLCV data from HyperLiquid...")
    df = fetch_ohlcv_data()
    
    if df is not None:
        # Save to CSV for further analysis
        filename = f"ohlcv_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df.to_csv(filename)
        print(f"\nData saved to {filename}") 