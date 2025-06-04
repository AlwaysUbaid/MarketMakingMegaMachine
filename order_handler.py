import logging
import threading
import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Union, Any

from hyperliquid.exchange import Exchange
from hyperliquid.info import Info



class OrderHandler:
    """Handles all order execution for Elysium Trading Platform"""
    
    def __init__(self, exchange: Optional[Exchange], info: Optional[Info]):
        self.exchange = exchange
        self.info = info
        self.wallet_address = None
        self.api_connector = None
        self.logger = logging.getLogger(__name__)

    def _check_connection(self):
        """Check if we have a valid exchange connection"""
        if not self.exchange or not self.info:
            if self.api_connector and self.api_connector.exchange:
                self.exchange = self.api_connector.exchange
                self.info = self.api_connector.info
            else:
                self.logger.error("Not connected to exchange")
                return False
        return True

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
        if not self._check_connection():
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
        if not self._check_connection():
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
        if not self._check_connection():
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
        if not self._check_connection():
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
        if not self._check_connection():
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
        if not self._check_connection():
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
        if not self._check_connection():
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
        if not self._check_connection():
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
        if not self._check_connection():
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
        if not self._check_connection():
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
        if not self._check_connection():
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
        if not self._check_connection():
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
        if not self._check_connection() or not self.info or not self.wallet_address:
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
            self.logger.error(f"Not connected to exchange. info={self.info}, wallet_address={self.wallet_address}")
            return []
            
        try:
            open_orders = self.info.open_orders(self.wallet_address)
            self.logger.info(f"[DEBUG] Fetched {len(open_orders)} open orders from API for wallet {self.wallet_address}: {open_orders}")
            if symbol:
                filtered = [order for order in open_orders if order['coin'] == symbol]
                self.logger.info(f"[DEBUG] Filtering open orders for symbol '{symbol}'. Available coins: {[order['coin'] for order in open_orders]}")
                self.logger.info(f"[DEBUG] Filtered open orders for symbol {symbol}: {filtered}")
                return filtered
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
        if not self._check_connection():
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
        if not self._check_connection():
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
        
# =======================================TWAPS==================================================

class TwapExecution:
    """Handles TWAP (Time-Weighted Average Price) order execution"""
    
    def __init__(self, order_handler, symbol: str, side: str, total_quantity: float, 
                duration_minutes: int, num_slices: int, price_limit: Optional[float] = None,
                is_perp: bool = False, leverage: int = 1):
        """
        Initialize TWAP execution
        
        Args:
            order_handler: The order handler object that executes orders
            symbol: Trading pair symbol
            side: 'buy' or 'sell'
            total_quantity: Total quantity to execute
            duration_minutes: Total duration in minutes
            num_slices: Number of slices to divide the order into
            price_limit: Optional price limit for each slice
            is_perp: Whether this is a perpetual futures order
            leverage: Leverage to use for perpetual orders
        """
        self.order_handler = order_handler
        self.symbol = symbol
        self.side = side.lower()
        self.total_quantity = total_quantity
        self.duration_minutes = duration_minutes
        self.num_slices = num_slices
        self.price_limit = price_limit
        self.is_perp = is_perp
        self.leverage = leverage
        
        # Calculate parameters
        self.quantity_per_slice = total_quantity / num_slices
        self.interval_seconds = (duration_minutes * 60) / num_slices
        
        # Initialize tracking variables
        self.is_running = False
        self.start_time = None
        self.end_time = None
        self.slices_executed = 0
        self.total_executed = 0.0
        self.average_price = 0.0
        self.execution_prices = []
        self.errors = []
        self.thread = None
        self.stop_event = threading.Event()
        
        self.logger = logging.getLogger(__name__)
    
    def start(self) -> bool:
        """Start the TWAP execution"""
        if self.is_running:
            self.logger.warning("TWAP execution already running")
            return False
        
        self.start_time = datetime.now()
        self.end_time = self.start_time + timedelta(minutes=self.duration_minutes)
        self.is_running = True
        self.stop_event.clear()
        
        self.logger.info(f"Starting TWAP execution for {self.total_quantity} {self.symbol} "
                        f"over {self.duration_minutes} minutes in {self.num_slices} slices")
        
        # Start execution thread
        self.thread = threading.Thread(target=self._execute_strategy)
        self.thread.daemon = True
        self.thread.start()
        
        return True
    
    def stop(self) -> bool:
        """Stop the TWAP execution"""
        if not self.is_running:
            self.logger.warning("TWAP execution not running")
            return False
        
        self.logger.info("Stopping TWAP execution")
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)
        
        self.is_running = False
        return True
    
    def get_status(self) -> Dict[str, Any]:
        """Get the current status of the TWAP execution"""
        return {
            "symbol": self.symbol,
            "side": self.side,
            "is_perp": self.is_perp,
            "total_quantity": self.total_quantity,
            "duration_minutes": self.duration_minutes,
            "num_slices": self.num_slices,
            "quantity_per_slice": self.quantity_per_slice,
            "interval_seconds": self.interval_seconds,
            "is_running": self.is_running,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "slices_executed": self.slices_executed,
            "total_executed": self.total_executed,
            "average_price": self.average_price,
            "remaining_quantity": self.total_quantity - self.total_executed,
            "completion_percentage": (self.slices_executed / self.num_slices) * 100 if self.num_slices > 0 else 0,
            "errors": self.errors
        }
    
    def _execute_strategy(self) -> None:
        """Execute the TWAP strategy - runs in a separate thread"""
        try:
            for slice_num in range(self.num_slices):
                # Check if we should stop
                if self.stop_event.is_set():
                    self.logger.info("TWAP execution stopped by user")
                    break
                
                # Execute slice
                slice_start_time = time.time()
                self._execute_slice(slice_num + 1)
                self.slices_executed += 1
                
                # Wait until the next interval, unless it's the last slice
                if slice_num < self.num_slices - 1:
                    # Calculate time to wait
                    elapsed = time.time() - slice_start_time
                    wait_time = max(0, self.interval_seconds - elapsed)
                    
                    # Wait, but check for stop event every second
                    for _ in range(int(wait_time)):
                        if self.stop_event.is_set():
                            self.logger.info("TWAP execution stopped during interval wait")
                            break
                        time.sleep(1)
                    
                    # Sleep any remaining fraction of a second
                    time.sleep(wait_time - int(wait_time))
            
            if self.slices_executed == self.num_slices:
                self.logger.info("TWAP execution completed successfully")
            else:
                self.logger.info(f"TWAP execution stopped after {self.slices_executed}/{self.num_slices} slices")
        
        except Exception as e:
            self.logger.error(f"Error in TWAP execution: {str(e)}")
            self.errors.append(str(e))
        
        finally:
            self.is_running = False
    
    def _execute_slice(self, slice_num: int) -> None:
        """Execute a single slice of the TWAP order"""
        try:
            self.logger.info(f"Executing TWAP slice {slice_num}/{self.num_slices} for {self.quantity_per_slice} {self.symbol}")
            
            # Execute the slice based on side and type (spot or perp)
            result = None
            
            if self.is_perp:
                # Perpetual order
                if self.side == 'buy':
                    if self.price_limit:
                        result = self.order_handler.perp_limit_buy(self.symbol, self.quantity_per_slice, 
                                                                self.price_limit, self.leverage)
                    else:
                        result = self.order_handler.perp_market_buy(self.symbol, self.quantity_per_slice, 
                                                                self.leverage)
                else:  # sell
                    if self.price_limit:
                        result = self.order_handler.perp_limit_sell(self.symbol, self.quantity_per_slice, 
                                                                self.price_limit, self.leverage)
                    else:
                        result = self.order_handler.perp_market_sell(self.symbol, self.quantity_per_slice, 
                                                                    self.leverage)
            else:
                # Spot order
                if self.side == 'buy':
                    if self.price_limit:
                        result = self.order_handler.limit_buy(self.symbol, self.quantity_per_slice, self.price_limit)
                    else:
                        result = self.order_handler.market_buy(self.symbol, self.quantity_per_slice)
                else:  # sell
                    if self.price_limit:
                        result = self.order_handler.limit_sell(self.symbol, self.quantity_per_slice, self.price_limit)
                    else:
                        result = self.order_handler.market_sell(self.symbol, self.quantity_per_slice)
            
            # Process the result
            if result and result["status"] == "ok":
                if "response" in result and "data" in result["response"] and "statuses" in result["response"]["data"]:
                    for status in result["response"]["data"]["statuses"]:
                        if "filled" in status:
                            filled = status["filled"]
                            executed_qty = float(filled["totalSz"])
                            executed_price = float(filled["avgPx"])
                            
                            self.total_executed += executed_qty
                            self.execution_prices.append(executed_price)
                            
                            # Update average price
                            if self.execution_prices:
                                self.average_price = sum(self.execution_prices) / len(self.execution_prices)
                            
                            self.logger.info(f"TWAP slice {slice_num} executed: {executed_qty} @ {executed_price}")
            else:
                error_msg = result.get("message", "Unknown error") if result else "No result returned"
                self.logger.error(f"TWAP slice {slice_num} failed: {error_msg}")
                self.errors.append(f"Slice {slice_num}: {error_msg}")
        
        except Exception as e:
            self.logger.error(f"Error executing TWAP slice {slice_num}: {str(e)}")
            self.errors.append(f"Slice {slice_num}: {str(e)}")


    # Now add the TWAP manager methods to the OrderHandler class
    def __init_twap_if_needed(self):
        """Initialize TWAP components if needed"""
        if not hasattr(self, 'active_twaps'):
            self.active_twaps = {}  # Dictionary to store active TWAP executions by ID
            self.completed_twaps = {}  # Dictionary to store completed TWAP executions by ID
            self.twap_id_counter = 1
            self.twap_lock = threading.Lock()  # Lock for thread safety

    def create_twap(self, symbol: str, side: str, quantity: float, 
                duration_minutes: int, num_slices: int, 
                price_limit: Optional[float] = None,
                is_perp: bool = False, leverage: int = 1) -> str:
        """
        Create a new TWAP execution
        
        Args:
            symbol: Trading pair symbol
            side: 'buy' or 'sell'
            quantity: Total quantity to execute
            duration_minutes: Total duration in minutes
            num_slices: Number of slices to divide the order into
            price_limit: Optional price limit for each slice
            is_perp: Whether this is a perpetual futures order
            leverage: Leverage to use for perpetual orders
            
        Returns:
            str: A unique ID for the TWAP execution
        """
        self.__init_twap_if_needed()
        
        with self.twap_lock:
            twap_id = f"twap_{datetime.now().strftime('%Y%m%d%H%M%S')}_{self.twap_id_counter}"
            self.twap_id_counter += 1
            
            twap = TwapExecution(
                self,
                symbol,
                side,
                quantity,
                duration_minutes,
                num_slices,
                price_limit,
                is_perp,
                leverage
            )
            
            self.active_twaps[twap_id] = twap
            self.logger.info(f"Created TWAP {twap_id} for {quantity} {symbol}")
            
            return twap_id

    def start_twap(self, twap_id: str) -> bool:
        """
        Start a TWAP execution
        
        Args:
            twap_id: The ID of the TWAP execution to start
            
        Returns:
            bool: True if started successfully, False otherwise
        """
        self.__init_twap_if_needed()
        
        with self.twap_lock:
            if twap_id not in self.active_twaps:
                self.logger.error(f"Cannot start TWAP {twap_id} - not found")
                return False
            
            twap = self.active_twaps[twap_id]
            success = twap.start()
            
            if success:
                self.logger.info(f"Started TWAP {twap_id}")
            else:
                self.logger.warning(f"Failed to start TWAP {twap_id}")
            
            return success

    def stop_twap(self, twap_id: str) -> bool:
        """
        Stop a TWAP execution
        
        Args:
            twap_id: The ID of the TWAP execution to stop
            
        Returns:
            bool: True if stopped successfully, False otherwise
        """
        self.__init_twap_if_needed()
        
        with self.twap_lock:
            if twap_id not in self.active_twaps:
                self.logger.error(f"Cannot stop TWAP {twap_id} - not found")
                return False
            
            twap = self.active_twaps[twap_id]
            success = twap.stop()
            
            if success:
                self.logger.info(f"Stopped TWAP {twap_id}")
                
                # Move to completed if it's no longer running
                if not twap.is_running:
                    self.completed_twaps[twap_id] = twap
                    del self.active_twaps[twap_id]
            else:
                self.logger.warning(f"Failed to stop TWAP {twap_id}")
            
            return success

    def get_twap_status(self, twap_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the status of a TWAP execution
        
        Args:
            twap_id: The ID of the TWAP execution
            
        Returns:
            Dict or None: The status of the TWAP execution, or None if not found
        """
        self.__init_twap_if_needed()
        
        with self.twap_lock:
            if twap_id in self.active_twaps:
                twap = self.active_twaps[twap_id]
                status = twap.get_status()
                status["id"] = twap_id
                status["status"] = "active"
                return status
            elif twap_id in self.completed_twaps:
                twap = self.completed_twaps[twap_id]
                status = twap.get_status()
                status["id"] = twap_id
                status["status"] = "completed"
                return status
            else:
                self.logger.error(f"Cannot get status for TWAP {twap_id} - not found")
                return None

    def list_twaps(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        List all TWAP executions
        
        Returns:
            Dict: A dictionary with 'active' and 'completed' lists of TWAP executions
        """
        self.__init_twap_if_needed()
        
        with self.twap_lock:
            active = []
            for twap_id, twap in self.active_twaps.items():
                status = twap.get_status()
                status["id"] = twap_id
                status["status"] = "active"
                active.append(status)
            
            completed = []
            for twap_id, twap in self.completed_twaps.items():
                status = twap.get_status()
                status["id"] = twap_id
                status["status"] = "completed"
                completed.append(status)
            
            return {
                "active": active,
                "completed": completed
            }

    def clean_completed_twaps(self) -> int:
        """
        Clean up completed TWAP executions
        
        Returns:
            int: The number of completed TWAP executions that were cleaned up
        """
        self.__init_twap_if_needed()
        
        with self.twap_lock:
            count = len(self.completed_twaps)
            self.completed_twaps.clear()
            self.logger.info(f"Cleaned up {count} completed TWAP executions")
            return count

    def stop_all_twaps(self) -> int:
        """
        Stop all active TWAP executions
        
        Returns:
            int: The number of TWAP executions that were stopped
        """
        self.__init_twap_if_needed()
        
        with self.twap_lock:
            count = 0
            twap_ids = list(self.active_twaps.keys())
            
            for twap_id in twap_ids:
                if self.stop_twap(twap_id):
                    count += 1
            
            self.logger.info(f"Stopped {count} TWAP executions")
            return count

    # Add methods to OrderHandler class
    OrderHandler.__init_twap_if_needed = __init_twap_if_needed
    OrderHandler.create_twap = create_twap
    OrderHandler.start_twap = start_twap
    OrderHandler.stop_twap = stop_twap
    OrderHandler.get_twap_status = get_twap_status
    OrderHandler.list_twaps = list_twaps
    OrderHandler.clean_completed_twaps = clean_completed_twaps
    OrderHandler.stop_all_twaps = stop_all_twaps
