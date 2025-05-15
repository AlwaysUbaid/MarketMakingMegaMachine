
import logging
import time

class BybitOrderHandler:
    """Handles order execution for Bybit"""
    
    def __init__(self, bybit_connector):
        self.connector = bybit_connector
        self.session = bybit_connector.session
        self.logger = logging.getLogger(__name__)
        
    def limit_buy(self, symbol, size, price):
        """Place a limit buy order"""
        if not self.session:
            return {"status": "error", "message": "Not connected to Bybit"}
            
        try:
            # Convert symbol format if needed
            bybit_symbol = self._format_symbol(symbol)
            
            self.logger.info(f"Placing Bybit limit buy: {size} {bybit_symbol} @ {price}")
            
            # Place the order
            result = self.session.place_order(
                category="linear",  # Assuming USDT perpetuals
                symbol=bybit_symbol,
                side="Buy",
                orderType="Limit",
                qty=str(size),
                price=str(price),
                timeInForce="GTC"
            )
            
            if result["retCode"] == 0:
                order_id = result["result"]["orderId"]
                self.logger.info(f"Bybit limit buy placed: order ID {order_id}")
                
                # Format result to match Hyperliquid format
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
            else:
                self.logger.error(f"Failed to place Bybit limit buy: {result['retMsg']}")
                return {"status": "error", "message": result["retMsg"]}
                
        except Exception as e:
            self.logger.error(f"Error placing Bybit limit buy: {str(e)}")
            return {"status": "error", "message": str(e)}
            
    def limit_sell(self, symbol, size, price):
        """Place a limit sell order"""
        if not self.session:
            return {"status": "error", "message": "Not connected to Bybit"}
            
        try:
            # Convert symbol format if needed
            bybit_symbol = self._format_symbol(symbol)
            
            self.logger.info(f"Placing Bybit limit sell: {size} {bybit_symbol} @ {price}")
            
            # Place the order
            result = self.session.place_order(
                category="linear",  # Assuming USDT perpetuals
                symbol=bybit_symbol,
                side="Sell",
                orderType="Limit",
                qty=str(size),
                price=str(price),
                timeInForce="GTC"
            )
            
            if result["retCode"] == 0:
                order_id = result["result"]["orderId"]
                self.logger.info(f"Bybit limit sell placed: order ID {order_id}")
                
                # Format result to match Hyperliquid format
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
            else:
                self.logger.error(f"Failed to place Bybit limit sell: {result['retMsg']}")
                return {"status": "error", "message": result["retMsg"]}
                
        except Exception as e:
            self.logger.error(f"Error placing Bybit limit sell: {str(e)}")
            return {"status": "error", "message": str(e)}
            
    def market_buy(self, symbol, size):
        """Execute a market buy order"""
        if not self.session:
            return {"status": "error", "message": "Not connected to Bybit"}
            
        try:
            # Convert symbol format if needed
            bybit_symbol = self._format_symbol(symbol)
            
            self.logger.info(f"Executing Bybit market buy: {size} {bybit_symbol}")
            
            # Place the order
            result = self.session.place_order(
                category="linear",  # Assuming USDT perpetuals
                symbol=bybit_symbol,
                side="Buy",
                orderType="Market",
                qty=str(size)
            )
            
            # Format and return result
            # [Implementation similar to limit orders]
            
        except Exception as e:
            self.logger.error(f"Error placing Bybit market buy: {str(e)}")
            return {"status": "error", "message": str(e)}
            
    def market_sell(self, symbol, size):
        """Execute a market sell order"""
        # [Similar implementation to market_buy]
        
    def cancel_order(self, symbol, order_id):
        """Cancel a specific order"""
        if not self.session:
            return {"status": "error", "message": "Not connected to Bybit"}
            
        try:
            # Convert symbol format if needed
            bybit_symbol = self._format_symbol(symbol)
            
            self.logger.info(f"Cancelling Bybit order {order_id} for {bybit_symbol}")
            
            # Cancel the order
            result = self.session.cancel_order(
                category="linear",  # Assuming USDT perpetuals
                symbol=bybit_symbol,
                orderId=str(order_id)
            )
            
            if result["retCode"] == 0:
                self.logger.info(f"Bybit order {order_id} cancelled successfully")
                return {"status": "ok", "message": ""}
            else:
                self.logger.error(f"Failed to cancel Bybit order {order_id}: {result['retMsg']}")
                return {"status": "error", "message": result["retMsg"]}
                
        except Exception as e:
            self.logger.error(f"Error cancelling Bybit order: {str(e)}")
            return {"status": "error", "message": str(e)}
            
    def get_open_orders(self, symbol=None):
        """Get all open orders, optionally filtered by symbol"""
        if not self.session:
            self.logger.error("Not connected to Bybit")
            return []
            
        try:
            # Convert symbol format if needed
            bybit_symbol = self._format_symbol(symbol) if symbol else None
            
            # Get open orders
            response = self.session.get_open_orders(
                category="linear",  # Assuming USDT perpetuals
                symbol=bybit_symbol
            )
            
            if response["retCode"] != 0:
                self.logger.error(f"Error getting open orders: {response['retMsg']}")
                return []
                
            # Transform Bybit format to match Hyperliquid format
            formatted_orders = []
            for order in response["result"]["list"]:
                formatted_orders.append({
                    "coin": order["symbol"],
                    "side": "B" if order["side"] == "Buy" else "S",
                    "sz": float(order["qty"]),
                    "limitPx": float(order["price"]) if order["price"] else 0,
                    "oid": order["orderId"],
                    "timestamp": int(order["createdTime"])
                })
                
            return formatted_orders
            
        except Exception as e:
            self.logger.error(f"Error fetching open orders: {str(e)}")
            return []
            
    def _format_symbol(self, symbol):
        """
        Convert symbol format between Hyperliquid and Bybit if needed
        
        Args:
            symbol: Symbol in Hyperliquid format (e.g., "UBTC/USDC")
            
        Returns:
            Symbol in Bybit format (e.g., "BTCUSDT")
        """
        # If symbol contains a slash, it's in the format "XXX/YYY"
        if '/' in symbol:
            base, quote = symbol.split('/')
            
            # Handle UBTC/USDC -> BTCUSDT mapping
            if base == "UBTC" and quote == "USDC":
                return "BTCUSDT"
            elif base == "UETH" and quote == "USDC":
                return "ETHUSDT"
            elif base == "USOL" and quote == "USDC":
                return "SOLUSDT"
            # Add more mappings as needed
            
            # Default to direct concatenation
            return f"{base}{quote}"
        
        # If no conversion needed, return as is
        return symbol