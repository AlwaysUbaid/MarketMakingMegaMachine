import requests
import json
import pandas as pd
from datetime import datetime

def get_spot_indices():
    """
    Retrieve all spot token indices and names from HyperLiquid exchange
    
    Returns:
        Dict with spot token information
    """
    
    # API endpoint
    url = "https://api.hyperliquid.xyz/info"
    
    # Request headers
    headers = {
        "Content-Type": "application/json"
    }
    
    # Request body for spot metadata
    payload = {
        "type": "spotMeta"
    }
    
    try:
        # Make the API request
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            
            # Print raw response to understand structure
            print("Raw spotMeta Response:")
            print(json.dumps(data, indent=2))
            
            spot_tokens = []
            
            # Extract spot token information
            if "universe" in data:
                for i, token_info in enumerate(data["universe"]):
                    spot_id = 10000 + i  # Spot ID calculation as per documentation
                    
                    spot_token = {
                        "index": i,
                        "spot_id": spot_id,
                        "name": token_info.get("name", "Unknown"),
                        "base_token": token_info.get("tokens", [None, None])[0],
                        "quote_token": token_info.get("tokens", [None, None])[1],
                        "tick_size": token_info.get("tickSize", "Unknown"),
                        "lot_size": token_info.get("lotSize", "Unknown")
                    }
                    spot_tokens.append(spot_token)
            
            return spot_tokens
            
        else:
            print(f"Error: {response.status_code}")
            print(response.text)
            return None
            
    except Exception as e:
        print(f"Error fetching spot indices: {str(e)}")
        return None

def display_spot_tokens(spot_tokens):
    """Display spot tokens in a formatted table"""
    if not spot_tokens:
        print("No spot tokens found")
        return
    
    print(f"\n{'='*80}")
    print("HYPERLIQUID SPOT TOKENS")
    print(f"{'='*80}")
    print(f"{'Index':<6} {'Spot ID':<8} {'Name':<20} {'Base':<10} {'Quote':<10} {'Tick Size':<12} {'Lot Size':<12}")
    print(f"{'-'*80}")
    
    for token in spot_tokens:
        print(f"{token['index']:<6} {token['spot_id']:<8} {token['name']:<20} "
              f"{token['base_token']:<10} {token['quote_token']:<10} "
              f"{token['tick_size']:<12} {token['lot_size']:<12}")
    
    print(f"{'-'*80}")
    print(f"Total spot tokens: {len(spot_tokens)}")

def save_to_csv(spot_tokens):
    """Save spot token data to CSV file"""
    if not spot_tokens:
        print("No data to save")
        return
    
    df = pd.DataFrame(spot_tokens)
    filename = f"spot_tokens_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    df.to_csv(filename, index=False)
    print(f"\nData saved to {filename}")

def get_perpetual_indices():
    """
    Also get perpetual token indices for comparison
    """
    url = "https://api.hyperliquid.xyz/info"
    headers = {"Content-Type": "application/json"}
    payload = {"type": "meta"}
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            
            perp_tokens = []
            if "universe" in data:
                for i, token_info in enumerate(data["universe"]):
                    perp_token = {
                        "index": i,
                        "perp_id": i,  # Perp ID is just the index
                        "name": token_info.get("name", "Unknown"),
                        "tick_size": token_info.get("tickSize", "Unknown"),
                        "lot_size": token_info.get("lotSize", "Unknown")
                    }
                    perp_tokens.append(perp_token)
            
            return perp_tokens
            
        else:
            print(f"Error getting perp data: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"Error fetching perp indices: {str(e)}")
        return None

def display_perpetual_tokens(perp_tokens):
    """Display perpetual tokens in a formatted table"""
    if not perp_tokens:
        print("No perpetual tokens found")
        return
    
    print(f"\n{'='*60}")
    print("HYPERLIQUID PERPETUAL TOKENS")
    print(f"{'='*60}")
    print(f"{'Index':<6} {'Perp ID':<8} {'Name':<20} {'Tick Size':<12} {'Lot Size':<12}")
    print(f"{'-'*60}")
    
    for token in perp_tokens:
        print(f"{token['index']:<6} {token['perp_id']:<8} {token['name']:<20} "
              f"{token['tick_size']:<12} {token['lot_size']:<12}")
    
    print(f"{'-'*60}")
    print(f"Total perpetual tokens: {len(perp_tokens)}")

if __name__ == "__main__":
    print("Fetching HyperLiquid token information...")
    
    # Get spot tokens
    print("\n1. Fetching Spot Tokens...")
    spot_tokens = get_spot_indices()
    
    if spot_tokens:
        display_spot_tokens(spot_tokens)
        save_to_csv(spot_tokens)
    
    # Get perpetual tokens for comparison
    print("\n2. Fetching Perpetual Tokens...")
    perp_tokens = get_perpetual_indices()
    
    if perp_tokens:
        display_perpetual_tokens(perp_tokens)
    
    print("\nDone!") 