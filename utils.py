import os
import sys
import time
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple

def setup_logging(log_level: int = logging.INFO, log_file: Optional[str] = None) -> logging.Logger:
    """Set up logging configuration"""
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Configure the root logger
    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Add file handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter(log_format))
        logging.getLogger().addHandler(file_handler)
    
    return logging.getLogger("elysium")

def format_number(number: float, decimal_places: int = 2) -> str:
    """Format a number with the specified decimal places"""
    return f"{number:.{decimal_places}f}"

def format_price(price: float) -> str:
    """Format a price with appropriate decimal places"""
    if price < 0.001:
        return f"{price:.8f}"
    elif price < 1:
        return f"{price:.6f}"
    elif price < 10:
        return f"{price:.4f}"
    else:
        return f"{price:.2f}"

def format_size(size: float) -> str:
    """Format a size with appropriate decimal places"""
    if size < 0.001:
        return f"{size:.8f}"
    elif size < 1:
        return f"{size:.4f}"
    else:
        return f"{size:.2f}"

def format_timestamp(timestamp: int) -> str:
    """Format a timestamp to date time string"""
    return datetime.fromtimestamp(timestamp / 1000).strftime("%Y-%m-%d %H:%M:%S")

def print_table(headers: List[str], rows: List[List[Any]], title: Optional[str] = None) -> None:
    """Print a formatted table to the console"""
    # Calculate column widths
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(cell)))
    
    # Print title if provided
    if title:
        print(f"\n{title}")
        print("=" * len(title))
    
    # Print headers
    header_str = " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
    print(header_str)
    print("-" * len(header_str))
    
    # Print rows
    for row in rows:
        row_str = " | ".join(str(cell).ljust(col_widths[i]) for i, cell in enumerate(row))
        print(row_str)

def load_fills_history() -> List[Dict[str, Any]]:
    """Load trading fills history from file"""
    fills = []
    try:
        if os.path.exists("fills"):
            with open("fills", "r") as f:
                for line in f:
                    fills.extend(json.loads(line.strip()))
    except Exception as e:
        logging.error(f"Error loading fills history: {str(e)}")
    
    return fills

def calculate_pnl_metrics(fills: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate PnL metrics from trading history"""
    if not fills:
        return {
            "total_trades": 0,
            "total_volume": 0,
            "total_pnl": 0,
            "win_count": 0,
            "loss_count": 0,
            "win_rate": 0,
            "avg_win": 0,
            "avg_loss": 0
        }
    
    total_trades = len(fills)
    total_volume = sum(float(fill["sz"]) * float(fill["px"]) for fill in fills)
    total_pnl = sum(float(fill.get("closedPnl", 0)) for fill in fills)
    
    # Separate wins and losses
    wins = [float(fill.get("closedPnl", 0)) for fill in fills if float(fill.get("closedPnl", 0)) > 0]
    losses = [float(fill.get("closedPnl", 0)) for fill in fills if float(fill.get("closedPnl", 0)) < 0]
    
    win_count = len(wins)
    loss_count = len(losses)
    win_rate = (win_count / total_trades) * 100 if total_trades > 0 else 0
    
    avg_win = sum(wins) / win_count if win_count > 0 else 0
    avg_loss = sum(losses) / loss_count if loss_count > 0 else 0
    
    return {
        "total_trades": total_trades,
        "total_volume": total_volume,
        "total_pnl": total_pnl,
        "win_count": win_count,
        "loss_count": loss_count,
        "win_rate": win_rate,
        "avg_win": avg_win,
        "avg_loss": avg_loss
    }

class Colors:
    """ANSI color codes for terminal output"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

class StatusIcons:
    """Status icons for terminal output"""
    SUCCESS = f"{Colors.GREEN}✓{Colors.END}"
    ERROR = f"{Colors.RED}✗{Colors.END}"
    WARNING = f"{Colors.YELLOW}⚠{Colors.END}"
    INFO = f"{Colors.BLUE}ℹ{Colors.END}"
    RUNNING = f"{Colors.GREEN}●{Colors.END}"
    STOPPED = f"{Colors.RED}●{Colors.END}"
    LOADING = f"{Colors.YELLOW}◌{Colors.END}"
    ARROW = f"{Colors.CYAN}➜{Colors.END}"