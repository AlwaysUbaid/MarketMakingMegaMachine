import logging
import time
import threading
from datetime import datetime
import json
import random

def setup_test_logging():
    """Set up logging for tests"""
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("cross_ex_test.log")
        ]
    )

class ExchangeSimulator:
    """Simulates exchange behavior for testing"""
    
    def __init__(self, exchange_id, base_price=None, volatility=0.001):
        self.logger = logging.getLogger(f"simulator.{exchange_id}")
        self.exchange_id = exchange_id
        self.base_price = base_price or random.uniform(60000, 65000)  # Default BTC price range
        self.volatility = volatility
        self.current_price = self.base_price
        self.orderbooks = {}
        self.balances = {
            "BTC": 1.0,
            "ETH": 10.0,
            "SOL": 100.0,
            "USDT": 100000.0,
            "USDC": 100000.0
        }
        
        # Start price simulation thread
        self.running = True
        self.thread = threading.Thread(target=self._simulate_prices, daemon=True)
        self.thread.start()
        
    def stop(self):
        """Stop the simulator"""
        self.running = False
        self.thread.join(timeout=1)
        
    def _simulate_prices(self):
        """Simulate price movements"""
        while self.running:
            # Random walk price movement
            price_change = random.normalvariate(0, self.volatility) * self.current_price
            self.current_price += price_change
            
            # Ensure price doesn't go negative
            self.current_price = max(self.current_price, 1.0)
            
            # Update orderbooks
            self._update_orderbooks()
            
            # Sleep a short time
            time.sleep(0.1)
            
    def _update_orderbooks(self):
        """Update orderbooks based on current price"""
        for symbol in self.orderbooks:
            # Calculate bid and ask
            spread = self.current_price * 0.0002  # 0.02% spread
            bid = self.current_price - spread/2
            ask = self.current_price + spread/2
            
            # Create orderbook
            self.orderbooks[symbol] = {
                "bids": [[bid, random.uniform(0.1, 1.0)] for _ in range(10)],
                "asks": [[ask, random.uniform(0.1, 1.0)] for _ in range(10)]
            }
            
            # Sort orderbook
            self.orderbooks[symbol]["bids"].sort(key=lambda x: x[0], reverse=True)
            self.orderbooks[symbol]["asks"].sort(key=lambda x: x[0])
            
    def get_market_data(self, symbol):
        """Get simulated market data"""
        # Ensure symbol exists in orderbooks
        if symbol not in self.orderbooks:
            self.orderbooks[symbol] = {
                "bids": [],
                "asks": []
            }
            self._update_orderbooks()
            
        orderbook = self.orderbooks[symbol]
        
        # Check if orderbook has data
        if not orderbook["bids"] or not orderbook["asks"]:
            return {"error": "Empty orderbook"}
            
        best_bid = orderbook["bids"][0][0]
        best_ask = orderbook["asks"][0][0]
        
        # Create market data
        return {
            "best_bid": best_bid,
            "best_ask": best_ask,
            "mid_price": (best_bid + best_ask) / 2,
            "order_book": {
                "b": orderbook["bids"],
                "a": orderbook["asks"]
            }
        }
        
    def get_balances(self):
        """Get simulated balances"""
        spot_balances = []
        
        for asset, total in self.balances.items():
            # Simulate some balance being in orders
            in_orders = total * random.uniform(0, 0.1)
            available = total - in_orders
            
            spot_balances.append({
                "asset": asset,
                "total": total,
                "available": available,
                "in_orders": in_orders
            })
            
        return {"spot": spot_balances}
        
    def place_order(self, symbol, side, order_type, size, price=None):
        """Simulate placing an order"""
        order_id = f"simorder_{int(time.time() * 1000)}_{random.randint(1000, 9999)}"
        
        # Adjust balances
        if side.lower() == "buy":
            quote = "USDT" if symbol.endswith("USDT") else "USDC"
            base = symbol.replace("USDT", "").replace("USDC", "")
            
            # Check if sufficient balance
            cost = size * (price or self.current_price)
            if cost > self.balances.get(quote, 0):
                return {"status": "error", "message": "Insufficient balance"}
                
            # Reduce quote balance, increase base balance
            self.balances[quote] -= cost
            self.balances[base] = self.balances.get(base, 0) + size
            
        else:  # sell
            base = symbol.replace("USDT", "").replace("USDC", "")
            quote = "USDT" if symbol.endswith("USDT") else "USDC"
            
            # Check if sufficient balance
            if size > self.balances.get(base, 0):
                return {"status": "error", "message": "Insufficient balance"}
                
            # Reduce base balance, increase quote balance
            self.balances[base] -= size
            self.balances[quote] = self.balances.get(quote, 0) + size * (price or self.current_price)
            
        # Return success
        return {
            "status": "ok",
            "message": "",
            "response": {
                "data": {
                    "statuses": [
                        {"resting": {"oid": order_id}}
                    ]
                }
            }
        }

def test_arbitrage_strategy():
    """Test the arbitrage strategy with simulated exchanges"""
    setup_test_logging()
    logger = logging.getLogger("test_arbitrage")
    
    try:
        # Create simulators with slight price difference
        hl_simulator = ExchangeSimulator("hyperliquid", base_price=60000)
        bybit_simulator = ExchangeSimulator("bybit", base_price=60050)  # 0.08% higher
        
        logger.info("Exchange simulators initialized")
        
        # Create exchange config
        from exchange_config import ExchangeConfig
        config = ExchangeConfig()
        
        # Create normalizer
        from market_data_normalizer import MarketDataNormalizer
        normalizer = MarketDataNormalizer()
        
        # Create delta engine
        from delta_engine import DeltaEngine
        delta_engine = DeltaEngine(config)
        
        # Create inventory tracker
        from inventory_tracker import InventoryTracker
        inventory_tracker = InventoryTracker(config)
        
        # Update balances in inventory tracker
        inventory_tracker.update_balances("hyperliquid", hl_simulator.get_balances())
        inventory_tracker.update_balances("bybit", bybit_simulator.get_balances())
        
        logger.info("Components initialized")
        
        # Test market data normalization
        symbol = "UBTC/USDC"
        bybit_symbol = "BTCUSDT"
        
        hl_market_data = hl_simulator.get_market_data(symbol)
        bybit_market_data = bybit_simulator.get_market_data(bybit_symbol)
        
        normalized_hl = normalizer.normalize_orderbook("hyperliquid", symbol, hl_market_data)
        normalized_bybit = normalizer.normalize_orderbook("bybit", symbol, bybit_market_data)
        
        logger.info(f"Normalized HL: {normalized_hl['best_bid']:.2f} / {normalized_hl['best_ask']:.2f}")
        logger.info(f"Normalized Bybit: {normalized_bybit['best_bid']:.2f} / {normalized_bybit['best_ask']:.2f}")
        
        # Update delta engine
        delta_engine.update_market_data("hyperliquid", symbol, normalized_hl)
        delta_engine.update_market_data("bybit", symbol, normalized_bybit)
        
        # Find arbitrage opportunities
        signals = delta_engine.find_arbitrage_opportunities()
        
        if signals:
            logger.info(f"Found {len(signals)} arbitrage opportunities")
            for signal in signals:
                logger.info(f"Signal: {signal['buy_exchange']} -> {signal['sell_exchange']}, "
                           f"Delta: {signal['delta_percentage']:.4f}%, "
                           f"Expected profit: {signal['expected_profit']:.8f}")
        else:
            logger.info("No arbitrage opportunities found")
            
        # Clean up
        hl_simulator.stop()
        bybit_simulator.stop()
        
        logger.info("Test completed successfully")
        
    except Exception as e:
        logger.error(f"Test error: {str(e)}", exc_info=True)

def main():
    """Main test function"""
    test_arbitrage_strategy()

if __name__ == "__main__":
    main()