from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
import uvicorn
import logging
from dotenv import load_dotenv
import os

from api_connector import ApiConnector
from order_handler import OrderHandler
from config_manager import ConfigManager
from strategy_selector import StrategySelector

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="MMMM Trading API",
    description="API for Market Making Mega Machine trading platform",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instances
api_connector = None
order_handler = None
config_manager = None
strategy_selector = None

# Pydantic models for request/response validation
class ConnectionRequest(BaseModel):
    wallet_address: str
    wallet_secret: str
    use_testnet: bool = False

class StrategyParams(BaseModel):
    params: Dict[str, Any]

class OrderRequest(BaseModel):
    symbol: str
    size: float
    price: Optional[float] = None
    order_type: str = "limit"
    leverage: Optional[int] = None
    slippage: float = 0.05

# Dependency to check if exchange is connected
async def get_exchange():
    if not api_connector or not api_connector.exchange:
        raise HTTPException(status_code=400, detail="Exchange not connected")
    return api_connector.exchange

# Initialize components
def initialize_components():
    global api_connector, order_handler, config_manager, strategy_selector
    config_manager = ConfigManager()
    api_connector = ApiConnector()
    order_handler = OrderHandler(None, None)
    strategy_selector = StrategySelector(api_connector, order_handler, config_manager)

# API Routes
@app.post("/connect")
async def connect_exchange(request: ConnectionRequest):
    """Connect to the exchange"""
    try:
        if api_connector.connect_hyperliquid(
            request.wallet_address,
            request.wallet_secret,
            request.use_testnet
        ):
            order_handler.exchange = api_connector.exchange
            order_handler.info = api_connector.info
            order_handler.api_connector = api_connector
            return {"status": "success", "message": "Connected to exchange"}
        else:
            raise HTTPException(status_code=400, detail="Failed to connect to exchange")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/balances")
async def get_balances(exchange = Depends(get_exchange)):
    """Get account balances"""
    try:
        balances = api_connector.get_balances()
        return {"status": "success", "data": balances}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/positions")
async def get_positions(exchange = Depends(get_exchange)):
    """Get open positions"""
    try:
        positions = api_connector.get_positions()
        return {"status": "success", "data": positions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/orders")
async def get_orders(symbol: Optional[str] = None, exchange = Depends(get_exchange)):
    """Get open orders"""
    try:
        orders = order_handler.get_open_orders(symbol)
        return {"status": "success", "data": orders}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/orders/market")
async def place_market_order(request: OrderRequest, exchange = Depends(get_exchange)):
    """Place a market order"""
    try:
        if request.order_type == "buy":
            result = order_handler.market_buy(request.symbol, request.size, request.slippage)
        else:
            result = order_handler.market_sell(request.symbol, request.size, request.slippage)
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/orders/limit")
async def place_limit_order(request: OrderRequest, exchange = Depends(get_exchange)):
    """Place a limit order"""
    try:
        if not request.price:
            raise HTTPException(status_code=400, detail="Price is required for limit orders")
        if request.order_type == "buy":
            result = order_handler.limit_buy(request.symbol, request.size, request.price)
        else:
            result = order_handler.limit_sell(request.symbol, request.size, request.price)
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/orders/{symbol}/{order_id}")
async def cancel_order(symbol: str, order_id: int, exchange = Depends(get_exchange)):
    """Cancel a specific order"""
    try:
        result = order_handler.cancel_order(symbol, order_id)
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/orders")
async def cancel_all_orders(symbol: Optional[str] = None, exchange = Depends(get_exchange)):
    """Cancel all orders"""
    try:
        result = order_handler.cancel_all_orders(symbol)
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/strategies")
async def list_strategies():
    """List available strategies"""
    try:
        strategies = strategy_selector.list_strategies()
        return {"status": "success", "data": strategies}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/strategies/{strategy_name}/params")
async def get_strategy_params(strategy_name: str):
    """Get parameters for a strategy"""
    try:
        params = strategy_selector.get_strategy_params(strategy_name)
        return {"status": "success", "data": params}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/strategies/{strategy_name}/start")
async def start_strategy(
    strategy_name: str,
    params: StrategyParams,
    background_tasks: BackgroundTasks,
    exchange = Depends(get_exchange)
):
    """Start a trading strategy"""
    try:
        success = strategy_selector.start_strategy(strategy_name, params.params)
        if success:
            return {"status": "success", "message": f"Started strategy: {strategy_name}"}
        else:
            raise HTTPException(status_code=400, detail=f"Failed to start strategy: {strategy_name}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/strategies/stop")
async def stop_strategy(exchange = Depends(get_exchange)):
    """Stop the currently running strategy"""
    try:
        success = strategy_selector.stop_strategy()
        if success:
            return {"status": "success", "message": "Strategy stopped"}
        else:
            raise HTTPException(status_code=400, detail="No active strategy to stop")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/strategies/status")
async def get_strategy_status(exchange = Depends(get_exchange)):
    """Get status of the currently running strategy"""
    try:
        status = strategy_selector.get_active_strategy()
        return {"status": "success", "data": status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Initialize components when the application starts
@app.on_event("startup")
async def startup_event():
    initialize_components()

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True) 