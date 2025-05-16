import logging
import threading
import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Union, Any

from hyperliquid.exchange import Exchange
from hyperliquid.info import Info

# Import our new Bybit connector
from bybit_connector import BybitConnector


class OrderHandler:
    """Handles all order execution for Elysium Trading Platform"""
    
    def __init__(self, exchange: Optional[Exchange], info: Optional[Info]):
        self.exchange = exchange
        self.info = info
        self.wallet_address = None
        self.logger = logging.getLogger(__name__)

        # Add Bybit-specific properties
        self.bybit_connector = None
        self.api_connector = None  # Will be set from main.py
        self.current_exchange = "hyperliquid"  # Default exchange
    
    def set_bybit_connector(self, bybit_connector: BybitConnector):
        """Set the Bybit connector"""
        self.bybit_connector = bybit_connector
    
    def set_exchange(self, exchange_name: str):
        """
        Set the current active exchange for order execution
        
        Args:
            exchange_name: "hyperliquid" or "bybit"
        """
        if exchange_name.lower() in ["hyperliquid", "bybit"]:
            self.current_exchange = exchange_name.lower()
            self.logger.info(f"Set current exchange to {self.current_exchange}")
        else:
            self.logger.error(f"Unknown exchange: {exchange_name}")

    # =================================Spot Trading==============================================
    def market_buy(self, symbol: str, size: float, slippage: float = 0.05) -> Dict[str, Any]:
        """
        Execute a market buy order
        
        Args:
            symbol: Trading pair symbol
            size: Order size
            slippage: Maximum acceptable slippage (default 5%)
            
        Returns:
            Order response dictionary
        """
        if not self.exchange:
            return {"status": "error", "message": "Not connected to exchange"}
            
        try:
            self.logger.info(f"Executing market buy: {size} {symbol}")
            result = self.exchange.market_open(symbol, True, size, None, slippage)
            
            if result["status"] == "ok":
                for status in result["response"]["data"]["statuses"]:
                    if "filled" in status:
                        filled = status["filled"]
                        self.logger.info(f"Market buy executed: {filled['totalSz']} @ {filled['avgPx']}")
                    elif "error" in status:
                        self.logger.error(f"Market buy error: {status['error']}")
            return result
        except Exception as e:
            self.logger.error(f"Error in market buy: {str(e)}")
            return {"status": "error", "message": str(e)}
            
    def market_sell(self, symbol: str, size: float, slippage: float = 0.05) -> Dict[str, Any]:
        """
        Execute a market sell order
        
        Args:
            symbol: Trading pair symbol
            size: Order size
            slippage: Maximum acceptable slippage (default 5%)
            
        Returns:
            Order response dictionary
        """
        if not self.exchange:
            return {"status": "error", "message": "Not connected to exchange"}
            
        try:
            self.logger.info(f"Executing market sell: {size} {symbol}")
            result = self.exchange.market_open(symbol, False, size, None, slippage)
            
            if result["status"] == "ok":
                for status in result["response"]["data"]["statuses"]:
                    if "filled" in status:
                        filled = status["filled"]
                        self.logger.info(f"Market sell executed: {filled['totalSz']} @ {filled['avgPx']}")
                    elif "error" in status:
                        self.logger.error(f"Market sell error: {status['error']}")
            return result
        except Exception as e:
            self.logger.error(f"Error in market sell: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def limit_buy(self, symbol: str, size: float, price: float) -> Dict[str, Any]:
        """
        Place a limit buy order
        
        Args:
            symbol: Trading pair symbol
            size: Order size
            price: Limit price
            
        Returns:
            Order response dictionary
        """
        if not self.exchange:
            return {"status": "error", "message": "Not connected to exchange"}
            
        try:
            self.logger.info(f"Placing limit buy: {size} {symbol} @ {price}")
            result = self.exchange.order(symbol, True, size, price, {"limit": {"tif": "Gtc"}})
            
            if result["status"] == "ok":
                status = result["response"]["data"]["statuses"][0]
                if "resting" in status:
                    oid = status["resting"]["oid"]
                    self.logger.info(f"Limit buy placed: order ID {oid}")
            return result
        except Exception as e:
            self.logger.error(f"Error in limit buy: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def limit_sell(self, symbol: str, size: float, price: float) -> Dict[str, Any]:
        """
        Place a limit sell order
        
        Args:
            symbol: Trading pair symbol
            size: Order size
            price: Limit price
            
        Returns:
            Order response dictionary
        """
        if not self.exchange:
            return {"status": "error", "message": "Not connected to exchange"}
            
        try:
            self.logger.info(f"Placing limit sell: {size} {symbol} @ {price}")
            result = self.exchange.order(symbol, False, size, price, {"limit": {"tif": "Gtc"}})
            
            if result["status"] == "ok":
                status = result["response"]["data"]["statuses"][0]
                if "resting" in status:
                    oid = status["resting"]["oid"]
                    self.logger.info(f"Limit sell placed: order ID {oid}")
            return result
        except Exception as e:
            self.logger.error(f"Error in limit sell: {str(e)}")
            return {"status": "error", "message": str(e)}
        
    # =================================Scaled Orders==============================================
    def _calculate_order_distribution(self, total_size: float, num_orders: int, skew: float) -> List[float]:
        """
        Calculate the size distribution across orders based on skew
        
        Args:
            total_size: Total order size
            num_orders: Number of orders to place
            skew: Skew factor (0 = linear, >0 = exponential)
            
        Returns:
            List of order sizes
        """
        if num_orders <= 0:
            return [total_size]
            
        if skew == 0:
            # Linear distribution - equal sizes
            return [total_size / num_orders] * num_orders
            
        # Exponential distribution based on skew
        # Higher skew = more weight on earlier orders
        weights = [pow(i+1, skew) for i in range(num_orders)]
        total_weight = sum(weights)
        
        return [total_size * (weight / total_weight) for weight in weights]
        
    def _calculate_price_levels(self, is_buy: bool, num_orders: int, start_price: float, end_price: float) -> List[float]:
        """
        Calculate price levels for orders
        
        Args:
            is_buy: True for buy orders, False for sell orders
            num_orders: Number of orders to place
            start_price: Starting price (highest for buys, lowest for sells)
            end_price: Ending price (lowest for buys, highest for sells)
            
        Returns:
            List of prices for each order
        """
        if num_orders <= 1:
            return [start_price]
            
        # Price step between orders
        step = (end_price - start_price) / (num_orders - 1)
        
        # Generate price levels
        return [start_price + (step * i) for i in range(num_orders)]
        
    def _format_size(self, symbol: str, size: float) -> float:
        """
        Format the order size according to exchange requirements
        
        Args:
            symbol: Trading pair symbol
            size: Order size
            
        Returns:
            Properly formatted size
        """
        try:
            # Get the metadata for the symbol
            meta = self.info.meta()
            
            # Find the symbol's info
            symbol_info = None
            for asset_info in meta["universe"]:
                if asset_info["name"] == symbol:
                    symbol_info = asset_info
                    break
                
            if symbol_info:
                # Format size based on symbol's decimal places
                sz_decimals = symbol_info.get("szDecimals", 2)
                return round(size, sz_decimals)
            
            # Default to 2 decimal places if symbol info not found
            return round(size, 2)
            
        except Exception as e:
            self.logger.warning(f"Error formatting size: {str(e)}. Using original size.")
            return size
        
    def _format_price(self, symbol: str, price: float) -> float:
        """
        Format the price according to exchange requirements
        
        Args:
            symbol: Trading pair symbol
            price: Price
            
        Returns:
            Properly formatted price
        """
        try:
            # Special handling for very large prices to avoid precision errors
            if price > 100_000:
                return round(price)
                
            # First round to 5 significant figures
            price_str = f"{price:.5g}"
            price_float = float(price_str)
            
            # Then apply additional rounding based on coin type
            coin = self.info.name_to_coin.get(symbol, symbol)
            if coin:
                asset_idx = self.info.coin_to_asset.get(coin)
                if asset_idx is not None:
                    is_spot = asset_idx >= 10_000
                    max_decimals = 8 if is_spot else 6
                    return round(price_float, max_decimals)
                
            # Default to 6 decimal places if we can't determine
            return round(price_float, 6)
            
        except Exception as e:
            self.logger.warning(f"Error formatting price: {str(e)}. Using original price.")
            return price
# ===================================== Scaled orders===========================================
    def scaled_orders(self, symbol: str, is_buy: bool, total_size: float, num_orders: int,
                    start_price: float, end_price: float, skew: float = 0,
                    order_type: Dict = None, reduce_only: bool = False, check_market: bool = True) -> Dict[str, Any]:
        """
        Place multiple orders across a price range with an optional skew
        
        Args:
            symbol: Trading pair symbol
            is_buy: True for buy, False for sell
            total_size: Total order size
            num_orders: Number of orders to place
            start_price: Starting price (higher for buys, lower for sells)
            end_price: Ending price (lower for buys, higher for sells)
            skew: Skew factor (0 = linear, >0 = exponential)
            order_type: Order type dict, defaults to GTC limit orders
            reduce_only: Whether orders should be reduce-only
            check_market: Whether to check market prices and adjust if needed
            
        Returns:
            Dict containing status and order responses
        """
        if not self.exchange:
            return {"status": "error", "message": "Not connected to exchange"}
        
        try:
            # Validate inputs
            if total_size <= 0:
                return {"status": "error", "message": "Total size must be greater than 0"}
                
            if num_orders <= 0:
                return {"status": "error", "message": "Number of orders must be greater than 0"}
                
            if start_price <= 0 or end_price <= 0:
                return {"status": "error", "message": "Prices must be greater than 0"}
                
            if skew < 0:
                return {"status": "error", "message": "Skew must be non-negative"}
                
            # Validate/adjust price direction based on order side
            if is_buy and start_price < end_price:
                self.logger.warning("For buy orders, start_price should be higher than end_price. Swapping values.")
                start_price, end_price = end_price, start_price
            elif not is_buy and start_price > end_price:
                self.logger.warning("For sell orders, start_price should be lower than end_price. Swapping values.")
                start_price, end_price = end_price, start_price
            
            # Default order type if not provided
            if order_type is None:
                order_type = {"limit": {"tif": "Gtc"}}
                
            # If check_market is true, get the current market data to validate prices
            if check_market:
                try:
                    # Get order book
                    order_book = self.info.l2_snapshot(symbol)
                    
                    if order_book and "levels" in order_book and len(order_book["levels"]) >= 2:
                        bid_levels = order_book["levels"][0]
                        ask_levels = order_book["levels"][1]
                        
                        if bid_levels and ask_levels:
                            best_bid = float(bid_levels[0]["px"])
                            best_ask = float(ask_levels[0]["px"])
                            
                            self.logger.info(f"Current market for {symbol}: Bid: {best_bid}, Ask: {best_ask}")
                            
                            # For buy orders, ensure we're not buying above the ask
                            if is_buy:
                                if start_price > best_ask * 1.05:  # Allow 5% above ask as maximum
                                    self.logger.warning(f"Start price {start_price} is too high. Limiting to 5% above ask: {best_ask * 1.05}")
                                    start_price = min(start_price, best_ask * 1.05)
                                
                                # Make sure end price is not above best ask
                                if end_price > best_ask:
                                    self.logger.warning(f"End price {end_price} is above best ask. Setting to best bid.")
                                    end_price = best_bid
                                    
                            # For sell orders, ensure we're not selling below the bid
                            else:
                                if start_price < best_bid * 0.95:  # Allow 5% below bid as minimum
                                    self.logger.warning(f"Start price {start_price} is too low. Limiting to 5% below bid: {best_bid * 0.95}")
                                    start_price = max(start_price, best_bid * 0.95)
                                    
                                # Make sure end price is not below best bid
                                if end_price < best_bid:
                                    self.logger.warning(f"End price {end_price} is below best bid. Setting to best ask.")
                                    end_price = best_ask
                except Exception as e:
                    self.logger.warning(f"Error checking market data: {str(e)}. Continuing with provided prices.")
                    
            # Calculate size and price for each order
            order_sizes = self._calculate_order_distribution(total_size, num_orders, skew)
            price_levels = self._calculate_price_levels(is_buy, num_orders, start_price, end_price)
            
            # Format sizes and prices to correct precision
            formatted_sizes = [self._format_size(symbol, s) for s in order_sizes]
            formatted_prices = [self._format_price(symbol, p) for p in price_levels]
            
            # Place orders
            self.logger.info(f"Placing {num_orders} {'buy' if is_buy else 'sell'} orders for {symbol} from {start_price} to {end_price} with total size {total_size}")
            
            order_results = []
            successful_orders = 0
            
            for i in range(num_orders):
                try:
                    result = self.exchange.order(
                        symbol, 
                        is_buy, 
                        formatted_sizes[i], 
                        formatted_prices[i], 
                        order_type, 
                        reduce_only
                    )
                    
                    order_results.append(result)
                    
                    if result["status"] == "ok":
                        successful_orders += 1
                        self.logger.info(f"Order {i+1}/{num_orders} placed: {formatted_sizes[i]} @ {formatted_prices[i]}")
                    else:
                        self.logger.error(f"Order {i+1}/{num_orders} failed: {result}")
                        
                    # Small delay to avoid rate limiting
                    time.sleep(0.1)
                    
                except Exception as e:
                    error_msg = f"Error placing order {i+1}/{num_orders}: {str(e)}"
                    self.logger.error(error_msg)
                    order_results.append({"status": "error", "message": error_msg})
            
            return {
                "status": "ok" if successful_orders > 0 else "error",
                "message": f"Successfully placed {successful_orders}/{num_orders} orders",
                "successful_orders": successful_orders,
                "total_orders": num_orders,
                "results": order_results,
                "sizes": formatted_sizes,
                "prices": formatted_prices
            }
        except Exception as e:
            self.logger.error(f"Error in scaled orders: {str(e)}")
            return {"status": "error", "message": str(e)}

    # Also, fix the _calculate_price_levels function to ensure the range is correct
    def _calculate_price_levels(self, is_buy: bool, num_orders: int, start_price: float, end_price: float) -> List[float]:
        """
        Calculate price levels for orders
        
        Args:
            is_buy: True for buy orders, False for sell orders
            num_orders: Number of orders to place
            start_price: Starting price (higher for buys, lower for sells)
            end_price: Ending price (lower for buys, higher for sells)
            
        Returns:
            List of prices for each order
        """
        if num_orders <= 1:
            return [start_price]
            
        # Calculate step size
        step = (end_price - start_price) / (num_orders - 1)
        
        # Generate prices
        prices = []
        for i in range(num_orders):
            price = start_price + step * i
            prices.append(price)
        
        return prices
# ================================ Perp Scaled Orders ==============================================
    def perp_scaled_orders(self, symbol: str, is_buy: bool, total_size: float, num_orders: int,
                         start_price: float, end_price: float, leverage: int = 1, skew: float = 0,
                         order_type: Dict = None, reduce_only: bool = False) -> Dict[str, Any]:
        """
        Place multiple perpetual orders across a price range with an optional skew
        
        Args:
            symbol: Trading pair symbol
            is_buy: True for buy, False for sell
            total_size: Total order size
            num_orders: Number of orders to place
            start_price: Starting price (higher for buys, lower for sells)
            end_price: Ending price (lower for buys, higher for sells)
            leverage: Leverage multiplier (default 1x)
            skew: Skew factor (0 = linear, >0 = exponential)
            order_type: Order type dict, defaults to GTC limit orders
            reduce_only: Whether orders should be reduce-only
            
        Returns:
            Dict containing status and order responses
        """
        if not self.exchange:
            return {"status": "error", "message": "Not connected to exchange"}
            
        try:
            # Set leverage first
            self._set_leverage(symbol, leverage)
            
            # Use the standard scaled orders implementation
            return self.scaled_orders(
                symbol, is_buy, total_size, num_orders, 
                start_price, end_price, skew, 
                order_type, reduce_only
            )
        except Exception as e:
            self.logger.error(f"Error in perpetual scaled orders: {str(e)}")
            return {"status": "error", "message": str(e)}
                
# =================================Perp Trading==============================================
    def perp_market_buy(self, symbol: str, size: float, leverage: int = 1, slippage: float = 0.05) -> Dict[str, Any]:
        """
        Execute a perpetual market buy order
        
        Args:
            symbol: Trading pair symbol (e.g., "BTC" or "ETH")
            size: Contract size
            leverage: Leverage multiplier (default 1x)
            slippage: Maximum acceptable slippage (default 5%)
            
        Returns:
            Order response dictionary
        """
        if not self.exchange:
            return {"status": "error", "message": "Not connected to exchange"}
            
        try:
            # Set leverage first
            self._set_leverage(symbol, leverage)
            
            self.logger.info(f"Executing perp market buy: {size} {symbol} with {leverage}x leverage")
            result = self.exchange.market_open(symbol, True, size, None, slippage)
            
            if result["status"] == "ok":
                for status in result["response"]["data"]["statuses"]:
                    if "filled" in status:
                        filled = status["filled"]
                        self.logger.info(f"Perp market buy executed: {filled['totalSz']} @ {filled['avgPx']}")
                    elif "error" in status:
                        self.logger.error(f"Perp market buy error: {status['error']}")
            return result
        except Exception as e:
            self.logger.error(f"Error in perp market buy: {str(e)}")
            return {"status": "error", "message": str(e)}
        
    def perp_market_sell(self, symbol: str, size: float, leverage: int = 1, slippage: float = 0.05) -> Dict[str, Any]:
        """
        Execute a perpetual market sell order
        
        Args:
            symbol: Trading pair symbol (e.g., "BTC" or "ETH")
            size: Contract size
            leverage: Leverage multiplier (default 1x)
            slippage: Maximum acceptable slippage (default 5%)
            
        Returns:
            Order response dictionary
        """
        if not self.exchange:
            return {"status": "error", "message": "Not connected to exchange"}
            
        try:
            # Set leverage first
            self._set_leverage(symbol, leverage)
            
            self.logger.info(f"Executing perp market sell: {size} {symbol} with {leverage}x leverage")
            result = self.exchange.market_open(symbol, False, size, None, slippage)
            
            if result["status"] == "ok":
                for status in result["response"]["data"]["statuses"]:
                    if "filled" in status:
                        filled = status["filled"]
                        self.logger.info(f"Perp market sell executed: {filled['totalSz']} @ {filled['avgPx']}")
                    elif "error" in status:
                        self.logger.error(f"Perp market sell error: {status['error']}")
            return result
        except Exception as e:
            self.logger.error(f"Error in perp market sell: {str(e)}")
            return {"status": "error", "message": str(e)}
        
    def perp_limit_buy(self, symbol: str, size: float, price: float, leverage: int = 1) -> Dict[str, Any]:
        """
        Place a perpetual limit buy order
        
        Args:
            symbol: Trading pair symbol (e.g., "BTC" or "ETH")
            size: Contract size
            price: Limit price
            leverage: Leverage multiplier (default 1x)
            
        Returns:
            Order response dictionary
        """
        if not self.exchange:
            return {"status": "error", "message": "Not connected to exchange"}
            
        try:
            # Set leverage first
            self._set_leverage(symbol, leverage)
            
            self.logger.info(f"Placing perp limit buy: {size} {symbol} @ {price} with {leverage}x leverage")
            result = self.exchange.order(symbol, True, size, price, {"limit": {"tif": "Gtc"}})
            
            if result["status"] == "ok":
                status = result["response"]["data"]["statuses"][0]
                if "resting" in status:
                    oid = status["resting"]["oid"]
                    self.logger.info(f"Perp limit buy placed: order ID {oid}")
            return result
        except Exception as e:
            self.logger.error(f"Error in perp limit buy: {str(e)}")
            return {"status": "error", "message": str(e)}
        
    def perp_limit_sell(self, symbol: str, size: float, price: float, leverage: int = 1) -> Dict[str, Any]:
        """
        Place a perpetual limit sell order
        
        Args:
            symbol: Trading pair symbol (e.g., "BTC" or "ETH")
            size: Contract size
            price: Limit price
            leverage: Leverage multiplier (default 1x)
            
        Returns:
            Order response dictionary
        """
        if not self.exchange:
            return {"status": "error", "message": "Not connected to exchange"}
            
        try:
            # Set leverage first
            self._set_leverage(symbol, leverage)
            
            self.logger.info(f"Placing perp limit sell: {size} {symbol} @ {price} with {leverage}x leverage")
            result = self.exchange.order(symbol, False, size, price, {"limit": {"tif": "Gtc"}})
            
            if result["status"] == "ok":
                status = result["response"]["data"]["statuses"][0]
                if "resting" in status:
                    oid = status["resting"]["oid"]
                    self.logger.info(f"Perp limit sell placed: order ID {oid}")
            return result
        except Exception as e:
            self.logger.error(f"Error in perp limit sell: {str(e)}")
            return {"status": "error", "message": str(e)}

    def close_position(self, symbol: str, slippage: float = 0.05) -> Dict[str, Any]:
        """
        Close an entire perpetual position for a symbol
        
        Args:
            symbol: Trading pair symbol
            slippage: Maximum acceptable slippage (default 5%)
            
        Returns:
            Order response dictionary
        """
        return self.market_close_position(symbol, slippage)

    def _set_leverage(self, symbol: str, leverage: int) -> Dict[str, Any]:
        """
        Set leverage for a symbol
        
        Args:
            symbol: Trading pair symbol
            leverage: Leverage multiplier
            
        Returns:
            Response dictionary
        """
        if not self.exchange:
            return {"status": "error", "message": "Not connected to exchange"}
            
        try:
            self.logger.info(f"Setting {leverage}x leverage for {symbol}")
            result = self.exchange.update_leverage(leverage, symbol)
            return result
        except Exception as e:
            self.logger.error(f"Error setting leverage: {str(e)}")
            return {"status": "error", "message": str(e)}
# =================================Order Cancellation==============================================
    def cancel_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """
        Cancel a specific order
        
        Args:
            symbol: Trading pair symbol
            order_id: Order ID to cancel
            
        Returns:
            Cancellation response dictionary
        """
        if not self.exchange:
            return {"status": "error", "message": "Not connected to exchange"}
            
        try:
            self.logger.info(f"Cancelling order {order_id} for {symbol}")
            result = self.exchange.cancel(symbol, order_id)
            
            if result["status"] == "ok":
                self.logger.info(f"Order {order_id} cancelled successfully")
            else:
                self.logger.error(f"Failed to cancel order {order_id}: {result}")
            return result
        except Exception as e:
            self.logger.error(f"Error cancelling order: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def cancel_all_orders(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        Cancel all open orders, optionally filtered by symbol
        
        Args:
            symbol: Optional trading pair symbol to filter cancellations
            
        Returns:
            Dictionary with cancellation results
        """
        if not self.exchange or not self.info or not self.wallet_address:
            return {"status": "error", "message": "Not connected to exchange"}
            
        try:
            self.logger.info(f"Cancelling all orders{' for ' + symbol if symbol else ''}")
            open_orders = self.info.open_orders(self.wallet_address)
            
            results = {"cancelled": 0, "failed": 0, "details": []}
            for order in open_orders:
                if symbol is None or order["coin"] == symbol:
                    result = self.cancel_order(order["coin"], order["oid"])
                    if result["status"] == "ok":
                        results["cancelled"] += 1
                    else:
                        results["failed"] += 1
                    results["details"].append(result)
                    
            self.logger.info(f"Cancelled {results['cancelled']} orders, {results['failed']} failed")
            return {"status": "ok", "data": results}
        except Exception as e:
            self.logger.error(f"Error cancelling all orders: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all open orders, optionally filtered by symbol
        
        Args:
            symbol: Optional trading pair symbol to filter results
            
        Returns:
            List of open orders
        """
        if not self.info or not self.wallet_address:
            self.logger.error("Not connected to exchange")
            return []
            
        try:
            open_orders = self.info.open_orders(self.wallet_address)
            
            if symbol:
                open_orders = [order for order in open_orders if order["coin"] == symbol]
                
            return open_orders
        except Exception as e:
            self.logger.error(f"Error getting open orders: {str(e)}")
            return []
    
    def market_close_position(self, symbol: str, slippage: float = 0.05) -> Dict[str, Any]:
        """
        Close an entire position for a symbol
        
        Args:
            symbol: Trading pair symbol
            slippage: Maximum acceptable slippage (default 5%)
            
        Returns:
            Order response dictionary
        """
        if not self.exchange:
            return {"status": "error", "message": "Not connected to exchange"}
            
        try:
            self.logger.info(f"Closing position for {symbol}")
            result = self.exchange.market_close(symbol, None, None, slippage)
            
            if result["status"] == "ok":
                for status in result["response"]["data"]["statuses"]:
                    if "filled" in status:
                        filled = status["filled"]
                        self.logger.info(f"Position closed: {filled['totalSz']} @ {filled['avgPx']}")
                    elif "error" in status:
                        self.logger.error(f"Position close error: {status['error']}")
            return result
        except Exception as e:
            self.logger.error(f"Error closing position: {str(e)}")
            return {"status": "error", "message": str(e)}
        
# ================================= Place Order ==========================================
    def place_order(self, symbol: str, side: str, size: float, price: float, order_type: str = "limit", time_in_force: str = "GTC") -> Dict[str, Any]:
        """
        Place an order with unified parameters
        
        Args:
            symbol: Trading pair symbol
            side: 'buy' or 'sell'
            size: Order size
            price: Order price
            order_type: Order type (limit, market)
            time_in_force: Time in force (GTC, IOC, etc.)
            
        Returns:
            Dictionary with order result and order ID if successful
        """
        if not self.exchange:
            return {"status": "error", "message": "Not connected to exchange"}
            
        try:
            self.logger.info(f"Placing {order_type} {side}: {size} {symbol} @ {price}")
            
            is_buy = side.lower() == "buy"
            
            # For limit orders
            if order_type.lower() == "limit":
                hyperliquid_order_type = {"limit": {"tif": "Gtc"}}
                if time_in_force.upper() == "IOC":
                    hyperliquid_order_type = {"limit": {"tif": "Ioc"}}
                elif time_in_force.upper() == "FOK":
                    hyperliquid_order_type = {"limit": {"tif": "Fok"}}
                
                result = self.exchange.order(symbol, is_buy, size, price, hyperliquid_order_type)
                return result  # Return the raw result for proper processing
                
            # For market orders
            elif order_type.lower() == "market":
                result = self.exchange.market_open(symbol, is_buy, size, None, 0.05)  # Use 5% slippage by default
                return result  # Return the raw result for proper processing
            
            # For other cases, return an error
            return {"status": "error", "message": f"Unsupported order type: {order_type}"}
            
        except Exception as e:
            self.logger.error(f"Error placing order: {str(e)}")
            return {"status": "error", "message": str(e)}
# ================================= Timestamped Orders ==========================================
    def get_timestamp(self):
        """
        Get the current timestamp in milliseconds
        
        Returns:
            int: Current timestamp in milliseconds
        """
        from hyperliquid.utils.signing import get_timestamp_ms
        return get_timestamp_ms()        
        
        # =================================Spot Trading for Bybit==============================================
    
    def bybit_market_buy(self, symbol: str, size: float) -> Dict[str, Any]:
        """
        Execute a market buy order on Bybit
        
        Args:
            symbol: Trading pair symbol
            size: Order size
            
        Returns:
            Order response dictionary
        """
        if not self.bybit_connector or not self.bybit_connector.http_client:
            return {"status": "error", "message": "Not connected to Bybit"}
            
        try:
            self.logger.info(f"Executing Bybit market buy: {size} {symbol}")
            
            # Normalize symbol format if needed (e.g., "BTC/USDT" -> "BTCUSDT")
            if "/" in symbol:
                base, quote = symbol.split("/")
                normalized_symbol = f"{base}{quote}"
            else:
                normalized_symbol = symbol
            
            # Determine category based on symbol
            category = self._get_bybit_category(symbol)
            
            result = self.bybit_connector.http_client.place_order(
                category=category,
                symbol=normalized_symbol,
                side="Buy",
                orderType="Market",
                qty=str(size),
                timeInForce="GTC"
            )
            
            if result["retCode"] == 0:
                self.logger.info(f"Bybit market buy executed successfully: {size} {symbol}")
                return {"status": "ok", "response": {"data": {"statuses": [{"filled": {"totalSz": size}}]}}}
            else:
                self.logger.error(f"Bybit market buy error: {result['retMsg']}")
                return {"status": "error", "message": result["retMsg"]}
                
        except Exception as e:
            self.logger.error(f"Error in Bybit market buy: {str(e)}")
            return {"status": "error", "message": str(e)}
            
    def bybit_market_sell(self, symbol: str, size: float) -> Dict[str, Any]:
        """
        Execute a market sell order on Bybit
        
        Args:
            symbol: Trading pair symbol
            size: Order size
            
        Returns:
            Order response dictionary
        """
        if not self.bybit_connector or not self.bybit_connector.http_client:
            return {"status": "error", "message": "Not connected to Bybit"}
            
        try:
            self.logger.info(f"Executing Bybit market sell: {size} {symbol}")
            
            # Normalize symbol format if needed
            if "/" in symbol:
                base, quote = symbol.split("/")
                normalized_symbol = f"{base}{quote}"
            else:
                normalized_symbol = symbol
            
            # Determine category based on symbol
            category = self._get_bybit_category(symbol)
            
            result = self.bybit_connector.http_client.place_order(
                category=category,
                symbol=normalized_symbol,
                side="Sell",
                orderType="Market",
                qty=str(size),
                timeInForce="GTC"
            )
            
            if result["retCode"] == 0:
                self.logger.info(f"Bybit market sell executed successfully: {size} {symbol}")
                return {"status": "ok", "response": {"data": {"statuses": [{"filled": {"totalSz": size}}]}}}
            else:
                self.logger.error(f"Bybit market sell error: {result['retMsg']}")
                return {"status": "error", "message": result["retMsg"]}
                
        except Exception as e:
            self.logger.error(f"Error in Bybit market sell: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def bybit_limit_buy(self, symbol: str, size: float, price: float) -> Dict[str, Any]:
        """
        Place a limit buy order on Bybit
        
        Args:
            symbol: Trading pair symbol
            size: Order size
            price: Limit price
            
        Returns:
            Order response dictionary
        """
        if not self.bybit_connector or not self.bybit_connector.http_client:
            return {"status": "error", "message": "Not connected to Bybit"}
            
        try:
            self.logger.info(f"Placing Bybit limit buy: {size} {symbol} @ {price}")
            
            # Normalize symbol format
            if "/" in symbol:
                base, quote = symbol.split("/")
                normalized_symbol = f"{base}{quote}"
            else:
                normalized_symbol = symbol
            
            # Determine category based on symbol
            category = self._get_bybit_category(symbol)
            
            result = self.bybit_connector.http_client.place_order(
                category=category,
                symbol=normalized_symbol,
                side="Buy",
                orderType="Limit",
                qty=str(size),
                price=str(price),
                timeInForce="GTC"
            )
            
            if result["retCode"] == 0:
                order_id = result["result"]["orderId"]
                self.logger.info(f"Bybit limit buy placed: order ID {order_id}")
                return {"status": "ok", "response": {"data": {"statuses": [{"resting": {"oid": order_id}}]}}}
            else:
                self.logger.error(f"Bybit limit buy error: {result['retMsg']}")
                return {"status": "error", "message": result["retMsg"]}
                
        except Exception as e:
            self.logger.error(f"Error in Bybit limit buy: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def bybit_limit_sell(self, symbol: str, size: float, price: float) -> Dict[str, Any]:
        """
        Place a limit sell order on Bybit
        
        Args:
            symbol: Trading pair symbol
            size: Order size
            price: Limit price
            
        Returns:
            Order response dictionary
        """
        if not self.bybit_connector or not self.bybit_connector.http_client:
            return {"status": "error", "message": "Not connected to Bybit"}
            
        try:
            self.logger.info(f"Placing Bybit limit sell: {size} {symbol} @ {price}")
            
            # Normalize symbol format
            if "/" in symbol:
                base, quote = symbol.split("/")
                normalized_symbol = f"{base}{quote}"
            else:
                normalized_symbol = symbol
            
            # Determine category based on symbol
            category = self._get_bybit_category(symbol)
            
            result = self.bybit_connector.http_client.place_order(
                category=category,
                symbol=normalized_symbol,
                side="Sell",
                orderType="Limit",
                qty=str(size),
                price=str(price),
                timeInForce="GTC"
            )
            
            if result["retCode"] == 0:
                order_id = result["result"]["orderId"]
                self.logger.info(f"Bybit limit sell placed: order ID {order_id}")
                return {"status": "ok", "response": {"data": {"statuses": [{"resting": {"oid": order_id}}]}}}
            else:
                self.logger.error(f"Bybit limit sell error: {result['retMsg']}")
                return {"status": "error", "message": result["retMsg"]}
                
        except Exception as e:
            self.logger.error(f"Error in Bybit limit sell: {str(e)}")
            return {"status": "error", "message": str(e)}

    # =================================Perp Trading for Bybit==============================================
    
    def bybit_perp_market_buy(self, symbol: str, size: float, leverage: int = 1) -> Dict[str, Any]:
        """
        Execute a perpetual market buy order on Bybit
        
        Args:
            symbol: Trading pair symbol
            size: Contract size
            leverage: Leverage multiplier (default 1x)
            
        Returns:
            Order response dictionary
        """
        if not self.bybit_connector or not self.bybit_connector.http_client:
            return {"status": "error", "message": "Not connected to Bybit"}
            
        try:
            # Set leverage first
            self._bybit_set_leverage(symbol, leverage)
            
            self.logger.info(f"Executing Bybit perp market buy: {size} {symbol} with {leverage}x leverage")
            
            # Normalize symbol format
            if "/" in symbol:
                base, quote = symbol.split("/")
                normalized_symbol = f"{base}{quote}"
            else:
                normalized_symbol = symbol
            
            # For perpetual, we use linear or inverse category
            category = "linear" if "USDT" in normalized_symbol else "inverse"
            
            result = self.bybit_connector.http_client.place_order(
                category=category,
                symbol=normalized_symbol,
                side="Buy",
                orderType="Market",
                qty=str(size),
                timeInForce="GTC"
            )
            
            if result["retCode"] == 0:
                self.logger.info(f"Bybit perp market buy executed successfully: {size} {symbol}")
                return {"status": "ok", "response": {"data": {"statuses": [{"filled": {"totalSz": size}}]}}}
            else:
                self.logger.error(f"Bybit perp market buy error: {result['retMsg']}")
                return {"status": "error", "message": result["retMsg"]}
                
        except Exception as e:
            self.logger.error(f"Error in Bybit perp market buy: {str(e)}")
            return {"status": "error", "message": str(e)}
        
    def bybit_perp_market_sell(self, symbol: str, size: float, leverage: int = 1) -> Dict[str, Any]:
        """
        Execute a perpetual market sell order on Bybit
        
        Args:
            symbol: Trading pair symbol
            size: Contract size
            leverage: Leverage multiplier (default 1x)
            
        Returns:
            Order response dictionary
        """
        if not self.bybit_connector or not self.bybit_connector.http_client:
            return {"status": "error", "message": "Not connected to Bybit"}
            
        try:
            # Set leverage first
            self._bybit_set_leverage(symbol, leverage)
            
            self.logger.info(f"Executing Bybit perp market sell: {size} {symbol} with {leverage}x leverage")
            
            # Normalize symbol format
            if "/" in symbol:
                base, quote = symbol.split("/")
                normalized_symbol = f"{base}{quote}"
            else:
                normalized_symbol = symbol
            
            # For perpetual, we use linear or inverse category
            category = "linear" if "USDT" in normalized_symbol else "inverse"
            
            result = self.bybit_connector.http_client.place_order(
                category=category,
                symbol=normalized_symbol,
                side="Sell",
                orderType="Market",
                qty=str(size),
                timeInForce="GTC"
            )
            
            if result["retCode"] == 0:
                self.logger.info(f"Bybit perp market sell executed successfully: {size} {symbol}")
                return {"status": "ok", "response": {"data": {"statuses": [{"filled": {"totalSz": size}}]}}}
            else:
                self.logger.error(f"Bybit perp market sell error: {result['retMsg']}")
                return {"status": "error", "message": result["retMsg"]}
                
        except Exception as e:
            self.logger.error(f"Error in Bybit perp market sell: {str(e)}")
            return {"status": "error", "message": str(e)}
        
    def bybit_perp_limit_buy(self, symbol: str, size: float, price: float, leverage: int = 1) -> Dict[str, Any]:
        """
        Place a perpetual limit buy order on Bybit
        
        Args:
            symbol: Trading pair symbol
            size: Contract size
            price: Limit price
            leverage: Leverage multiplier (default 1x)
            
        Returns:
            Order response dictionary
        """
        if not self.bybit_connector or not self.bybit_connector.http_client:
            return {"status": "error", "message": "Not connected to Bybit"}
            
        try:
            # Set leverage first
            self._bybit_set_leverage(symbol, leverage)
            
            self.logger.info(f"Placing Bybit perp limit buy: {size} {symbol} @ {price} with {leverage}x leverage")
            
            # Normalize symbol format
            if "/" in symbol:
                base, quote = symbol.split("/")
                normalized_symbol = f"{base}{quote}"
            else:
                normalized_symbol = symbol
            
            # For perpetual, we use linear or inverse category
            category = "linear" if "USDT" in normalized_symbol else "inverse"
            
            result = self.bybit_connector.http_client.place_order(
                category=category,
                symbol=normalized_symbol,
                side="Buy",
                orderType="Limit",
                qty=str(size),
                price=str(price),
                timeInForce="GTC"
            )
            
            if result["retCode"] == 0:
                order_id = result["result"]["orderId"]
                self.logger.info(f"Bybit perp limit buy placed: order ID {order_id}")
                return {"status": "ok", "response": {"data": {"statuses": [{"resting": {"oid": order_id}}]}}}
            else:
                self.logger.error(f"Bybit perp limit buy error: {result['retMsg']}")
                return {"status": "error", "message": result["retMsg"]}
                
        except Exception as e:
            self.logger.error(f"Error in Bybit perp limit buy: {str(e)}")
            return {"status": "error", "message": str(e)}
        
    def bybit_perp_limit_sell(self, symbol: str, size: float, price: float, leverage: int = 1) -> Dict[str, Any]:
        """
        Place a perpetual limit sell order on Bybit
        
        Args:
            symbol: Trading pair symbol
            size: Contract size
            price: Limit price
            leverage: Leverage multiplier (default 1x)
            
        Returns:
            Order response dictionary
        """
        if not self.bybit_connector or not self.bybit_connector.http_client:
            return {"status": "error", "message": "Not connected to Bybit"}
            
        try:
            # Set leverage first
            self._bybit_set_leverage(symbol, leverage)
            
            self.logger.info(f"Placing Bybit perp limit sell: {size} {symbol} @ {price} with {leverage}x leverage")
            
            # Normalize symbol format
            if "/" in symbol:
                base, quote = symbol.split("/")
                normalized_symbol = f"{base}{quote}"
            else:
                normalized_symbol = symbol
            
            # For perpetual, we use linear or inverse category
            category = "linear" if "USDT" in normalized_symbol else "inverse"
            
            result = self.bybit_connector.http_client.place_order(
                category=category,
                symbol=normalized_symbol,
                side="Sell",
                orderType="Limit",
                qty=str(size),
                price=str(price),
                timeInForce="GTC"
            )
            
            if result["retCode"] == 0:
                order_id = result["result"]["orderId"]
                self.logger.info(f"Bybit perp limit sell placed: order ID {order_id}")
                return {"status": "ok", "response": {"data": {"statuses": [{"resting": {"oid": order_id}}]}}}
            else:
                self.logger.error(f"Bybit perp limit sell error: {result['retMsg']}")
                return {"status": "error", "message": result["retMsg"]}
                
        except Exception as e:
            self.logger.error(f"Error in Bybit perp limit sell: {str(e)}")
            return {"status": "error", "message": str(e)}

    def bybit_close_position(self, symbol: str) -> Dict[str, Any]:
        """
        Close an entire perpetual position for a symbol on Bybit
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            Order response dictionary
        """
        if not self.bybit_connector or not self.bybit_connector.http_client:
            return {"status": "error", "message": "Not connected to Bybit"}
            
        try:
            self.logger.info(f"Closing Bybit position for {symbol}")
            
            # Normalize symbol format
            if "/" in symbol:
                base, quote = symbol.split("/")
                normalized_symbol = f"{base}{quote}"
            else:
                normalized_symbol = symbol
            
            # For perpetual, we use linear or inverse category
            category = "linear" if "USDT" in normalized_symbol else "inverse"
            
            # First, get the position
            positions = self.bybit_connector.get_positions()
            position = next((p for p in positions if p["symbol"] == normalized_symbol), None)
            
            if not position or float(position["size"]) == 0:
                self.logger.warning(f"No position found for {symbol}")
                return {"status": "error", "message": "No position found"}
            
            # Determine side for closing (opposite of position)
            size = abs(float(position["size"]))
            side = "Sell" if float(position["size"]) > 0 else "Buy"
            
            # Place market order to close
            result = self.bybit_connector.http_client.place_order(
                category=category,
                symbol=normalized_symbol,
                side=side,
                orderType="Market",
                qty=str(size),
                reduceOnly=True,
                timeInForce="GTC"
            )
            
            if result["retCode"] == 0:
                self.logger.info(f"Bybit position closed successfully: {size} {symbol}")
                return {"status": "ok", "response": {"data": {"statuses": [{"filled": {"totalSz": size}}]}}}
            else:
                self.logger.error(f"Bybit position close error: {result['retMsg']}")
                return {"status": "error", "message": result["retMsg"]}
                
        except Exception as e:
            self.logger.error(f"Error closing Bybit position: {str(e)}")
            return {"status": "error", "message": str(e)}

    def _bybit_set_leverage(self, symbol: str, leverage: int) -> Dict[str, Any]:
        """
        Set leverage for a symbol on Bybit
        
        Args:
            symbol: Trading pair symbol
            leverage: Leverage multiplier
            
        Returns:
            Response dictionary
        """
        if not self.bybit_connector or not self.bybit_connector.http_client:
            return {"status": "error", "message": "Not connected to Bybit"}
            
        try:
            # Normalize symbol format
            if "/" in symbol:
                base, quote = symbol.split("/")
                normalized_symbol = f"{base}{quote}"
            else:
                normalized_symbol = symbol
            
            # For perpetual, we use linear or inverse category
            category = "linear" if "USDT" in normalized_symbol else "inverse"
            
            self.logger.info(f"Setting {leverage}x leverage for {symbol} on Bybit")
            
            result = self.bybit_connector.http_client.set_leverage(
                category=category,
                symbol=normalized_symbol,
                buyLeverage=str(leverage),
                sellLeverage=str(leverage)
            )
            
            if result["retCode"] == 0:
                self.logger.info(f"Leverage set to {leverage}x for {symbol}")
                return {"status": "ok"}
            else:
                self.logger.error(f"Set leverage error: {result['retMsg']}")
                return {"status": "error", "message": result["retMsg"]}
                
        except Exception as e:
            self.logger.error(f"Error setting leverage on Bybit: {str(e)}")
            return {"status": "error", "message": str(e)}

    # =================================Order Management for Bybit==============================================
    
    def bybit_cancel_order(self, symbol: str, order_id: str) -> Dict[str, Any]:
        """
        Cancel a specific order on Bybit
        
        Args:
            symbol: Trading pair symbol
            order_id: Order ID to cancel
            
        Returns:
            Cancellation response dictionary
        """
        if not self.bybit_connector or not self.bybit_connector.http_client:
            return {"status": "error", "message": "Not connected to Bybit"}
            
        try:
            self.logger.info(f"Cancelling Bybit order {order_id} for {symbol}")
            
            # Normalize symbol format
            if "/" in symbol:
                base, quote = symbol.split("/")
                normalized_symbol = f"{base}{quote}"
            else:
                normalized_symbol = symbol
            
            # Determine category based on symbol
            category = self._get_bybit_category(symbol)
            
            result = self.bybit_connector.http_client.cancel_order(
                category=category,
                symbol=normalized_symbol,
                orderId=order_id
            )
            
            if result["retCode"] == 0:
                self.logger.info(f"Bybit order {order_id} cancelled successfully")
                return {"status": "ok"}
            else:
                self.logger.error(f"Bybit cancel order error: {result['retMsg']}")
                return {"status": "error", "message": result["retMsg"]}
                
        except Exception as e:
            self.logger.error(f"Error cancelling Bybit order: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def bybit_cancel_all_orders(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        Cancel all open orders on Bybit, optionally filtered by symbol
        
        Args:
            symbol: Optional trading pair symbol to filter cancellations
            
        Returns:
            Dictionary with cancellation results
        """
        if not self.bybit_connector or not self.bybit_connector.http_client:
            return {"status": "error", "message": "Not connected to Bybit"}
            
        try:
            symbol_str = f" for {symbol}" if symbol else ""
            self.logger.info(f"Cancelling all Bybit orders{symbol_str}")
            
            # Normalize symbol format if provided
            normalized_symbol = None
            if symbol:
                if "/" in symbol:
                    base, quote = symbol.split("/")
                    normalized_symbol = f"{base}{quote}"
                else:
                    normalized_symbol = symbol
            
            # Cancel orders for each category
            categories = ["spot", "linear", "inverse"]
            results = {"cancelled": 0, "failed": 0, "details": []}
            
            for category in categories:
                try:
                    cancel_args = {"category": category}
                    if normalized_symbol:
                        cancel_args["symbol"] = normalized_symbol
                    
                    result = self.bybit_connector.http_client.cancel_all_orders(**cancel_args)
                    
                    if result["retCode"] == 0:
                        # Count cancelled orders
                        if "list" in result["result"]:
                            cancelled_count = len(result["result"]["list"])
                            results["cancelled"] += cancelled_count
                            results["details"].append({
                                "category": category,
                                "count": cancelled_count
                            })
                    else:
                        results["failed"] += 1
                        results["details"].append({
                            "category": category,
                            "error": result["retMsg"]
                        })
                except Exception as e:
                    self.logger.warning(f"Error cancelling {category} orders: {str(e)}")
                    results["failed"] += 1
                    results["details"].append({
                        "category": category,
                        "error": str(e)
                    })
            
            self.logger.info(f"Cancelled {results['cancelled']} Bybit orders, {results['failed']} failures")
            return {"status": "ok", "data": results}
                
        except Exception as e:
            self.logger.error(f"Error cancelling all Bybit orders: {str(e)}")
            return {"status": "error", "message": str(e)}

    # =================================Exchange Routing==============================================

    def market_buy(self, symbol: str, size: float, slippage: float = 0.05) -> Dict[str, Any]:
        """
        Execute a market buy order on the current exchange
        
        Args:
            symbol: Trading pair symbol
            size: Order size
            slippage: Maximum acceptable slippage (default 5%)
            
        Returns:
            Order response dictionary
        """
        if self.current_exchange == "bybit":
            return self.bybit_market_buy(symbol, size)
        else:
            return super().market_buy(symbol, size, slippage)
            
    def market_sell(self, symbol: str, size: float, slippage: float = 0.05) -> Dict[str, Any]:
        """
        Execute a market sell order on the current exchange
        
        Args:
            symbol: Trading pair symbol
            size: Order size
            slippage: Maximum acceptable slippage (default 5%)
            
        Returns:
            Order response dictionary
        """
        if self.current_exchange == "bybit":
            return self.bybit_market_sell(symbol, size)
        else:
            return super().market_sell(symbol, size, slippage)
    
    def limit_buy(self, symbol: str, size: float, price: float) -> Dict[str, Any]:
        """
        Place a limit buy order on the current exchange
        
        Args:
            symbol: Trading pair symbol
            size: Order size
            price: Limit price
            
        Returns:
            Order response dictionary
        """
        if self.current_exchange == "bybit":
            return self.bybit_limit_buy(symbol, size, price)
        else:
            return super().limit_buy(symbol, size, price)
    
    def limit_sell(self, symbol: str, size: float, price: float) -> Dict[str, Any]:
        """
        Place a limit sell order on the current exchange
        
        Args:
            symbol: Trading pair symbol
            size: Order size
            price: Limit price
            
        Returns:
            Order response dictionary
        """
        if self.current_exchange == "bybit":
            return self.bybit_limit_sell(symbol, size, price)
        else:
            return super().limit_sell(symbol, size, price)
    
    def perp_market_buy(self, symbol: str, size: float, leverage: int = 1, slippage: float = 0.05) -> Dict[str, Any]:
        """
        Execute a perpetual market buy order on the current exchange
        
        Args:
            symbol: Trading pair symbol
            size: Contract size
            leverage: Leverage multiplier (default 1x)
            slippage: Maximum acceptable slippage (default 5%)
            
        Returns:
            Order response dictionary
        """
        if self.current_exchange == "bybit":
            return self.bybit_perp_market_buy(symbol, size, leverage)
        else:
            return super().perp_market_buy(symbol, size, leverage, slippage)
        
    def perp_market_sell(self, symbol: str, size: float, leverage: int = 1, slippage: float = 0.05) -> Dict[str, Any]:
        """
        Execute a perpetual market sell order on the current exchange
        
        Args:
            symbol: Trading pair symbol
            size: Contract size
            leverage: Leverage multiplier (default 1x)
            slippage: Maximum acceptable slippage (default 5%)
            
        Returns:
            Order response dictionary
        """
        if self.current_exchange == "bybit":
            return self.bybit_perp_market_sell(symbol, size, leverage)
        else:
            return super().perp_market_sell(symbol, size, leverage, slippage)
        
    def perp_limit_buy(self, symbol: str, size: float, price: float, leverage: int = 1) -> Dict[str, Any]:
        """
        Place a perpetual limit buy order on the current exchange
        
        Args:
            symbol: Trading pair symbol
            size: Contract size
            price: Limit price
            leverage: Leverage multiplier (default 1x)
            
        Returns:
            Order response dictionary
        """
        if self.current_exchange == "bybit":
            return self.bybit_perp_limit_buy(symbol, size, price, leverage)
        else:
            return super().perp_limit_buy(symbol, size, price, leverage)
        
    def perp_limit_sell(self, symbol: str, size: float, price: float, leverage: int = 1) -> Dict[str, Any]:
        """
        Place a perpetual limit sell order on the current exchange
        
        Args:
            symbol: Trading pair symbol
            size: Contract size
            price: Limit price
            leverage: Leverage multiplier (default 1x)
            
        Returns:
            Order response dictionary
        """
        if self.current_exchange == "bybit":
            return self.bybit_perp_limit_sell(symbol, size, price, leverage)
        else:
            return super().perp_limit_sell(symbol, size, price, leverage)

    def close_position(self, symbol: str, slippage: float = 0.05) -> Dict[str, Any]:
        """
        Close an entire perpetual position for a symbol
        
        Args:
            symbol: Trading pair symbol
            slippage: Maximum acceptable slippage (default 5%)
            
        Returns:
            Order response dictionary
        """
        if self.current_exchange == "bybit":
            return self.bybit_close_position(symbol)
        else:
            return super().close_position(symbol, slippage)
    
    def cancel_order(self, symbol: str, order_id: Union[int, str]) -> Dict[str, Any]:
        """
        Cancel a specific order
        
        Args:
            symbol: Trading pair symbol
            order_id: Order ID to cancel
            
        Returns:
            Cancellation response dictionary
        """
        if self.current_exchange == "bybit":
            return self.bybit_cancel_order(symbol, str(order_id))
        else:
            return super().cancel_order(symbol, order_id)
    
    def cancel_all_orders(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        Cancel all open orders, optionally filtered by symbol
        
        Args:
            symbol: Optional trading pair symbol to filter cancellations
            
        Returns:
            Dictionary with cancellation results
        """
        if self.current_exchange == "bybit":
            return self.bybit_cancel_all_orders(symbol)
        else:
            return super().cancel_all_orders(symbol)
    
    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all open orders, optionally filtered by symbol
        
        Args:
            symbol: Optional trading pair symbol to filter results
            
        Returns:
            List of open orders
        """
        if self.current_exchange == "bybit":
            return self.bybit_connector.get_open_orders(symbol)
        else:
            return super().get_open_orders(symbol)

    # =================================Helper Methods==============================================
    
    def _get_bybit_category(self, symbol: str) -> str:
        """
        Determine the market category for a symbol on Bybit
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            Category string: "spot", "linear", or "inverse"
        """
        # Handle spot format: "BTC/USDT" -> "spot"
        if "/" in symbol:
            return "spot"
        
        # Handle perpetual formats
        if symbol.endswith("USDT"):
            return "linear"
        elif symbol.endswith("USD"):
            return "inverse"
        
        # Default to spot for unknown formats
        return "spot"
