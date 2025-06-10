import requests
import json
import pandas as pd
from datetime import datetime

def get_token_metadata():
    """Get token metadata from HyperLiquid API"""
    url = "https://api.hyperliquid.xyz/info"
    payload = {
        "type": "meta"
    }
    headers = {
        "Content-Type": "application/json"
    }
    
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        data = response.json()
        # Create a mapping of token indices to names
        token_map = {}
        for i, token in enumerate(data.get('universe', [])):
            token_map[i] = token['name']
        return token_map
    else:
        print(f"Error fetching token metadata: {response.status_code}")
        return {}

def get_spot_indices():
    """Get spot token indices and names from HyperLiquid"""
    url = "https://api.hyperliquid.xyz/info"
    
    # First get token metadata to map token IDs to names
    token_meta_payload = {
        "type": "meta"
    }
    headers = {
        "Content-Type": "application/json"
    }
    
    # Get token metadata first
    token_response = requests.post(url, json=token_meta_payload, headers=headers)
    token_map = {}
    if token_response.status_code == 200:
        token_data = token_response.json()
        for i, token in enumerate(token_data.get('universe', [])):
            token_map[i] = token['name']
    
    # Get spot metadata
    spot_payload = {
        "type": "spotMeta"
    }
    
    response = requests.post(url, json=spot_payload, headers=headers)
    if response.status_code == 200:
        data = response.json()
        spot_tokens = []
        
        for spot in data.get('universe', []):
            token_id = spot.get('tokenId')
            token_name = token_map.get(token_id, 'Unknown') if token_id is not None else 'Unknown'
            
            spot_tokens.append({
                'index': spot['index'],
                'spot_id': 10000 + spot['index'],
                'name': spot['name'],
                'token_name': token_name,
                'sz_decimals': spot.get('szDecimals', 'Unknown'),
                'wei_decimals': spot.get('weiDecimals', 'Unknown'),
                'token_id': str(token_id) if token_id is not None else 'Unknown',
                'is_canonical': spot.get('isCanonical', False),
                'evm_contract': spot.get('evmContract', None)
            })
        
        # Create DataFrame
        df = pd.DataFrame(spot_tokens)
        
        # Display spot tokens
        print("\n" + "="*120)
        print("HYPERLIQUID SPOT TOKENS")
        print("="*120)
        print(f"{'Index':<6} {'Spot ID':<8} {'Name':<20} {'Token Name':<20} {'Decimals':<15} {'Token ID':<40}")
        print("-"*120)
        
        for _, row in df.iterrows():
            decimals = f"{row['sz_decimals']}/{row['wei_decimals']}"
            print(f"{row['index']:<6} {row['spot_id']:<8} {row['name']:<20} {row['token_name']:<20} {decimals:<15} {row['token_id']:<40}")
        
        print("-"*120)
        print(f"Total spot tokens: {len(spot_tokens)}")
        
        # Save to CSV
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"spot_tokens_{timestamp}.csv"
        df.to_csv(filename, index=False)
        print(f"\nData saved to {filename}")
        
        return spot_tokens
    else:
        print(f"Error: {response.status_code}")
        return None

def get_perpetual_tokens():
    """Get perpetual token indices and names"""
    url = "https://api.hyperliquid.xyz/info"
    payload = {
        "type": "meta"
    }
    headers = {
        "Content-Type": "application/json"
    }
    
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        data = response.json()
        perp_tokens = []
        
        for i, token in enumerate(data.get('universe', [])):
            perp_tokens.append({
                'index': i,
                'perp_id': i,
                'name': token['name'],
                'tick_size': token.get('tickSize', 'Unknown'),
                'lot_size': token.get('lotSize', 'Unknown')
            })
        
        # Display perpetual tokens
        print("\n" + "="*60)
        print("HYPERLIQUID PERPETUAL TOKENS")
        print("="*60)
        print(f"{'Index':<6} {'Perp ID':<8} {'Name':<20} {'Tick Size':<12} {'Lot Size':<12}")
        print("-"*60)
        
        for token in perp_tokens:
            print(f"{token['index']:<6} {token['perp_id']:<8} {token['name']:<20} {token['tick_size']:<12} {token['lot_size']:<12}")
        
        print("-"*60)
        print(f"Total perpetual tokens: {len(perp_tokens)}")
        
        return perp_tokens
    else:
        print(f"Error: {response.status_code}")
        return None

if __name__ == "__main__":
    print("1. Fetching Spot Tokens...")
    get_spot_indices()
    
    print("\n2. Fetching Perpetual Tokens...")
    get_perpetual_tokens()
    
    print("\nDone!") 