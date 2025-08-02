#!/bin/bash

# Sir Tim the Timely - Raspberry Pi Setup Script
# This script sets up the Discord bot on a Raspberry Pi with automatic startup

set -e

echo "🤖 Setting up Sir Tim the Timely on Raspberry Pi..."

# Configuration
BOT_DIR="/home/pi/Sir-Tim-the-Timely"
SERVICE_NAME="sir-tim-bot"
PYTHON_BIN="/usr/bin/python3"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as pi user
if [ "$USER" != "pi" ]; then
    print_error "This script should be run as the 'pi' user"
    exit 1
fi

# Update system packages
print_status "Updating system packages..."
sudo apt update
sudo apt upgrade -y

# Install required system packages
print_status "Installing required system packages..."
sudo apt install -y python3 python3-pip python3-venv git curl

# Create bot directory if it doesn't exist
if [ ! -d "$BOT_DIR" ]; then
    print_status "Cloning Sir Tim the Timely repository..."
    git clone https://github.com/0xCUB3/Sir-Tim-the-Timely.git "$BOT_DIR"
fi

# Navigate to bot directory
cd "$BOT_DIR"

print_status "Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
print_status "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create data directory
print_status "Creating data directory..."
mkdir -p data

# Set up environment file
if [ ! -f ".env" ]; then
    print_status "Creating environment file template..."
    cat > .env << EOF
# Discord Bot Configuration
TOKEN=your_discord_token_here
GEMINI_API_KEY=your_gemini_api_key_here

# Database Configuration
DATABASE_PATH=./data/deadlines.db

# Bot Configuration
LOG_LEVEL=INFO
USE_SIMPLIFIED_INTERFACE=true
DEFAULT_TIMEZONE=US/Eastern

# Optional: MIT Deadlines URL (uses default if not set)
# MIT_DEADLINES_URL=https://firstyear.mit.edu/orientation/countdown-to-campus-before-you-arrive/critical-summer-actions-and-deadlines/

# Optional: Reminder Configuration
# DAILY_REMINDER_TIME=09:00
# WEEKLY_DIGEST_TIME=09:00
# REMINDER_ROLE_ID=your_role_id_here
EOF
    
    print_warning "Please edit .env file with your actual tokens before starting the bot!"
fi

# Create systemd service file
print_status "Setting up systemd service..."
mkdir -p ~/.config/systemd/user

# Update service file with correct paths
sed "s|/home/pi/Sir-Tim-the-Timely|$BOT_DIR|g" deployment/sir-tim-bot.service > ~/.config/systemd/user/sir-tim-bot.service
sed -i "s|/usr/bin/python3|$BOT_DIR/venv/bin/python|g" ~/.config/systemd/user/sir-tim-bot.service

# Reload systemd and enable service
systemctl --user daemon-reload
systemctl --user enable sir-tim-bot

# Create startup script
print_status "Creating startup script..."
cat > start_bot.sh << 'EOF'
#!/bin/bash
cd /home/pi/Sir-Tim-the-Timely
source venv/bin/activate
python main.py
EOF
chmod +x start_bot.sh

# Create stop script
cat > stop_bot.sh << 'EOF'
#!/bin/bash
systemctl --user stop sir-tim-bot
EOF
chmod +x stop_bot.sh

# Create status script
cat > status_bot.sh << 'EOF'
#!/bin/bash
systemctl --user status sir-tim-bot
EOF
chmod +x status_bot.sh

# Create log viewing script
cat > logs_bot.sh << 'EOF'
#!/bin/bash
journalctl --user -u sir-tim-bot -f
EOF
chmod +x logs_bot.sh

print_status "✅ Setup complete!"
echo
print_status "Next steps:"
echo "1. Edit the .env file with your Discord token and Gemini API key:"
echo "   nano $BOT_DIR/.env"
echo
echo "2. Start the bot:"
echo "   systemctl --user start sir-tim-bot"
echo
echo "3. Check status:"
echo "   systemctl --user status sir-tim-bot"
echo
echo "4. View logs:"
echo "   journalctl --user -u sir-tim-bot -f"
echo
print_status "Useful commands:"
echo "• Start bot:    systemctl --user start sir-tim-bot"
echo "• Stop bot:     systemctl --user stop sir-tim-bot"
echo "• Restart bot:  systemctl --user restart sir-tim-bot"
echo "• View logs:    journalctl --user -u sir-tim-bot -f"
echo "• Bot status:   systemctl --user status sir-tim-bot"
echo
print_status "The bot will automatically start on system boot."
echo
print_warning "Remember to configure your GitHub repository secrets for CI/CD!"
echo "Required secrets: PI_HOST, PI_USERNAME, PI_SSH_KEY, PI_PORT, PI_BOT_PATH"
