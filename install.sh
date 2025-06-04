#!/bin/bash

# MMMM Trading Platform Installation Script
# This script installs the MMMM platform and all its components

# Function to log messages
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Function to handle errors
handle_error() {
    log "ERROR: $1"
    exit 1
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    handle_error "Please run as root"
fi

# Create necessary directories
log "Creating directories..."
mkdir -p /usr/local/bin/mmmm
mkdir -p /var/log/mmmm
mkdir -p /etc/mmmm

# Copy emergency scripts
log "Installing emergency scripts..."
cp cancel_all_orders.sh /usr/local/bin/mmmm-cancel-all
chmod +x /usr/local/bin/mmmm-cancel-all

# Create systemd service file
log "Creating systemd service..."
cat > /etc/systemd/system/mmmm.service << EOL
[Unit]
Description=MMMM Trading Bot
After=network.target

[Service]
Type=simple
User=trading
WorkingDirectory=/home/trading/mmmm
ExecStart=/usr/bin/python3 /home/trading/mmmm/main.py -v --log-file /var/log/mmmm/mmmm.log
ExecStop=/usr/local/bin/mmmm-cancel-all
Restart=on-failure
RestartSec=30s
StandardOutput=append:/var/log/mmmm/systemd-output.log
StandardError=append:/var/log/mmmm/systemd-error.log

[Install]
WantedBy=multi-user.target
EOL

# Create monitoring script
log "Creating monitoring script..."
cat > /usr/local/bin/mmmm-monitor << EOL
#!/bin/bash

# MMMM Monitoring Script
# Monitors logs for important events and triggers alerts

LOG_DIR="/var/log/mmmm"
ALERT_EMAIL="admin@example.com"

# Check for auto-cancellation events
check_auto_cancel() {
    if grep -q "Triggering auto-cancel-all routine" \$LOG_DIR/*.log; then
        echo "Auto-cancellation triggered - Check strategy status" | mail -s "MMMM Alert" \$ALERT_EMAIL
    fi
}

# Check for error patterns
check_errors() {
    if grep -q "ERROR" \$LOG_DIR/*.log; then
        echo "Errors detected in MMMM logs" | mail -s "MMMM Alert" \$ALERT_EMAIL
    fi
}

# Main monitoring loop
while true; do
    check_auto_cancel
    check_errors
    sleep 60
done
EOL

chmod +x /usr/local/bin/mmmm-monitor

# Create monitoring service
log "Creating monitoring service..."
cat > /etc/systemd/system/mmmm-monitor.service << EOL
[Unit]
Description=MMMM Monitoring Service
After=network.target

[Service]
Type=simple
User=trading
ExecStart=/usr/local/bin/mmmm-monitor
Restart=always
RestartSec=60s

[Install]
WantedBy=multi-user.target
EOL

# Set up log rotation
log "Setting up log rotation..."
cat > /etc/logrotate.d/mmmm << EOL
/var/log/mmmm/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0640 trading trading
}
EOL

# Reload systemd
log "Reloading systemd..."
systemctl daemon-reload

# Enable services
log "Enabling services..."
systemctl enable mmmm.service
systemctl enable mmmm-monitor.service

log "Installation completed successfully"
log "Please configure your API credentials in /etc/mmmm/config.json"
log "Then start the service with: systemctl start mmmm" 