#!/bin/bash

# MMMM Trading Bot Installation Script
# This script sets up the MMMM trading bot for deployment

# Check for root privileges if installing systemd service
if [ "$1" == "--system" ] && [ "$EUID" -ne 0 ]; then
    echo "System installation requires root privileges"
    echo "Please run: sudo $0 --system"
    exit 1
fi

echo "===== MMMM Trading Bot Installation ====="
echo

# Create directory structure
mkdir -p logs
mkdir -p strategies
mkdir -p configs

# Make scripts executable
chmod +x run_ubtc_mm.sh
chmod +x start_mmmm_service.sh
chmod +x stop_mmmm_service.sh
chmod +x run_strategy.py

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Copy the ubtc_mm.py strategy to strategies folder
if [ -f "ubtc_mm.py" ]; then
    cp ubtc_mm.py strategies/
    echo "UBTC market making strategy installed successfully"
else
    echo "Warning: ubtc_mm.py not found in current directory."
    echo "Please make sure to place your strategy files in the 'strategies' directory."
fi

# Check if dontshareconfig.py exists, create a template if not
if [ ! -f "dontshareconfig.py" ]; then
    echo "Creating dontshareconfig.py template..."
    cat > dontshareconfig.py << EOL
# Mainnet account credentials
mainnet_wallet = ""  # Your mainnet wallet address
mainnet_secret = ""  # Your mainnet private key

# Testnet account credentials
testnet_wallet = ""  # Your testnet wallet address
testnet_secret = ""  # Your testnet private key
EOL
    echo "Created dontshareconfig.py - PLEASE EDIT WITH YOUR API CREDENTIALS"
fi

# Check if we're installing as a system service
if [ "$1" == "--system" ]; then
    echo "Installing systemd service..."
    
    # Copy service file
    cp mmmm-ubtc.service /etc/systemd/system/
    
    # Create logs directory if installing as system service
    mkdir -p /var/log/mmmm
    
    # Reload systemd manager
    systemctl daemon-reload
    
    echo "Systemd service installed. You can now manage the bot with:"
    echo "  sudo systemctl start mmmm-ubtc.service  # Start the bot"
    echo "  sudo systemctl stop mmmm-ubtc.service   # Stop the bot"
    echo "  sudo systemctl enable mmmm-ubtc.service # Enable boot startup"
    echo "  sudo systemctl status mmmm-ubtc.service # Check bot status"
else
    echo "Local installation complete."
    echo
    echo "To run the UBTC market making strategy:"
    echo "  ./run_ubtc_mm.sh        # For mainnet"
    echo "  ./run_ubtc_mm.sh --testnet  # For testnet"
    echo
    echo "To run any strategy in background mode:"
    echo "  ./start_mmmm_service.sh ubtc_mm      # For mainnet"
    echo "  ./start_mmmm_service.sh ubtc_mm --testnet  # For testnet"
    echo
    echo "To stop a running strategy service:"
    echo "  ./stop_mmmm_service.sh ubtc_mm"
fi

echo
echo "IMPORTANT: Before running, make sure to update dontshareconfig.py with your wallet credentials!"
echo "===== Installation Complete ====="