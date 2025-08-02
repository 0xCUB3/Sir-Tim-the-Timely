#!/bin/bash

# Complete Raspberry Pi Setup Script for Sir Tim the Timely
# Run this script on your fresh Raspberry Pi OS installation

set -e  # Exit on any error

echo "=================================================="
echo "🍓 RASPBERRY PI SETUP FOR SIR TIM THE TIMELY"
echo "=================================================="

# Function to print step headers
print_step() {
    echo ""
    echo "🔧 STEP $1: $2"
    echo "----------------------------------------"
}

# Check if running as the correct user
if [ "$USER" != "skula" ]; then
    echo "⚠️  Warning: This script expects to be run as user 'skula'"
    echo "Current user: $USER"
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

print_step "1" "Updating system packages"
sudo apt update && sudo apt upgrade -y

print_step "2" "Installing required system packages"
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    curl \
    wget \
    htop \
    nano \
    sqlite3 \
    systemd \
    rsync

print_step "3" "Installing Python dependencies globally"
python3 -m pip install --user --upgrade pip setuptools wheel

print_step "4" "Setting up Git configuration"
echo "Please configure Git with your credentials:"
read -p "Enter your Git username: " git_username
read -p "Enter your Git email: " git_email
git config --global user.name "$git_username"
git config --global user.email "$git_email"

print_step "5" "Setting up GitHub authentication"
echo "Choose GitHub authentication method:"
echo "1) Personal Access Token (Recommended for private repos)"
echo "2) SSH Key"
read -p "Enter choice (1 or 2): " auth_choice

if [ "$auth_choice" = "1" ]; then
    echo "Setting up Personal Access Token authentication..."
    git config --global credential.helper store
    echo "You'll need to enter your token when cloning the repository"
elif [ "$auth_choice" = "2" ]; then
    echo "Setting up SSH Key authentication..."
    if [ ! -f ~/.ssh/id_ed25519 ]; then
        ssh-keygen -t ed25519 -C "$git_email"
        echo "📋 Your SSH public key (add this to GitHub):"
        cat ~/.ssh/id_ed25519.pub
        echo ""
        read -p "Press Enter after adding the key to GitHub..."
    else
        echo "SSH key already exists"
    fi
fi

print_step "6" "Cloning Sir Tim repository"
BOT_DIR="/home/$USER/Sir-Tim-the-Timely"
if [ ! -d "$BOT_DIR" ]; then
    echo "Choose clone method:"
    echo "1) HTTPS (for Personal Access Token)"
    echo "2) SSH (for SSH Key)"
    read -p "Enter choice (1 or 2): " clone_choice
    
    if [ "$clone_choice" = "1" ]; then
        git clone https://github.com/0xCUB3/Sir-Tim-the-Timely.git "$BOT_DIR"
    else
        git clone git@github.com:0xCUB3/Sir-Tim-the-Timely.git "$BOT_DIR"
    fi
else
    echo "Repository already exists at $BOT_DIR"
fi

print_step "7" "Installing Python dependencies"
cd "$BOT_DIR"
python3 -m pip install --user -r requirements.txt

print_step "8" "Setting up environment variables"
ENV_FILE="$BOT_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
    echo "Creating environment file..."
    cat > "$ENV_FILE" << 'EOF'
# Discord Bot Configuration
TOKEN=your_discord_token_here
GEMINI_API_KEY=your_gemini_api_key_here

# Database Configuration
DATABASE_PATH=./data/deadlines.db

# Bot Configuration
LOG_LEVEL=DEBUG
USE_SIMPLIFIED_INTERFACE=true
DEFAULT_TIMEZONE=US/Eastern
EOF
    echo "✅ Environment file created at $ENV_FILE"
    echo "⚠️  IMPORTANT: Edit $ENV_FILE with your actual tokens!"
else
    echo "Environment file already exists"
fi

print_step "9" "Setting up database directory"
mkdir -p "$BOT_DIR/data"
echo "✅ Database directory created"

print_step "10" "Installing systemd service"
# Update service file with correct user and paths
SERVICE_FILE="$BOT_DIR/deployment/sir-tim-bot.service"
SYSTEMD_DIR="$HOME/.config/systemd/user"
mkdir -p "$SYSTEMD_DIR"

# Copy and customize service file
cp "$SERVICE_FILE" "$SYSTEMD_DIR/"
sed -i "s|/home/skula|/home/$USER|g" "$SYSTEMD_DIR/sir-tim-bot.service"
sed -i "s|User=skula|User=$USER|g" "$SYSTEMD_DIR/sir-tim-bot.service"
sed -i "s|Group=skula|Group=$USER|g" "$SYSTEMD_DIR/sir-tim-bot.service"

# Enable lingering for user services
sudo loginctl enable-linger "$USER"

# Reload systemd and enable service
systemctl --user daemon-reload
systemctl --user enable sir-tim-bot.service

echo "✅ Systemd service installed and enabled"

print_step "11" "Setting up log monitoring aliases"
BASHRC_FILE="$HOME/.bashrc"
if ! grep -q "sir-tim-logs" "$BASHRC_FILE"; then
    cat >> "$BASHRC_FILE" << 'EOF'

# Sir Tim bot monitoring aliases
alias sir-tim-status='systemctl --user status sir-tim-bot'
alias sir-tim-logs='journalctl --user -u sir-tim-bot -f'
alias sir-tim-logs-recent='journalctl --user -u sir-tim-bot -n 50'
alias sir-tim-start='systemctl --user start sir-tim-bot'
alias sir-tim-stop='systemctl --user stop sir-tim-bot'
alias sir-tim-restart='systemctl --user restart sir-tim-bot'
EOF
    echo "✅ Log monitoring aliases added to ~/.bashrc"
fi

print_step "12" "Final setup verification"
echo "Checking Python installation..."
python3 --version
echo "Checking pip packages..."
python3 -m pip list --user | grep -E "(hikari|google|aiosqlite)" || echo "Some packages may not be installed yet"
echo "Checking service status..."
systemctl --user status sir-tim-bot --no-pager || echo "Service not started yet (this is normal)"

echo ""
echo "=================================================="
echo "🎉 SETUP COMPLETE!"
echo "=================================================="
echo ""
echo "📝 NEXT STEPS:"
echo "1. Edit environment variables: nano $ENV_FILE"
echo "2. Add your Discord token and Gemini API key"
echo "3. Start the bot: systemctl --user start sir-tim-bot"
echo "4. Check logs: journalctl --user -u sir-tim-bot -f"
echo ""
echo "🔧 USEFUL COMMANDS:"
echo "• sir-tim-status    - Check service status"
echo "• sir-tim-logs      - Follow live logs"
echo "• sir-tim-restart   - Restart the bot"
echo "• sir-tim-stop      - Stop the bot"
echo ""
echo "📁 Bot directory: $BOT_DIR"
echo "🔧 Service file: $SYSTEMD_DIR/sir-tim-bot.service"
echo "📄 Environment file: $ENV_FILE"
echo ""
echo "Happy botting! 🤖"
