#!/bin/bash

# Quick deployment test script for Sir Tim the Timely
# This script helps test the deployment setup locally

set -e

echo "🧪 Testing Sir Tim the Timely deployment setup..."

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_status() {
    echo -e "${GREEN}[✅]${NC} $1"
}

print_error() {
    echo -e "${RED}[❌]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[⚠️]${NC} $1"
}

# Test 1: Check required files
echo "📁 Checking required files..."

required_files=(
    "bot.py"
    "main.py"
    "requirements.txt"
    ".env.example"
    "deployment/setup_pi.sh"
    "deployment/sir-tim-bot.service"
    "deployment/README.md"
    ".github/workflows/deploy.yml"
    ".github/workflows/test.yml"
)

for file in "${required_files[@]}"; do
    if [ -f "$file" ]; then
        print_status "$file exists"
    else
        print_error "$file missing"
        exit 1
    fi
done

# Test 2: Check Python syntax
echo ""
echo "🐍 Checking Python syntax..."
python3 -m py_compile bot.py
python3 -m py_compile main.py
find src -name "*.py" -exec python3 -m py_compile {} \;
print_status "Python syntax check passed"

# Test 3: Check dependencies
echo ""
echo "📦 Checking dependencies..."
if [ -f "requirements.txt" ]; then
    print_status "requirements.txt found"
    echo "Dependencies:"
    cat requirements.txt | grep -v "^#" | grep -v "^$" | while read line; do
        echo "  • $line"
    done
else
    print_error "requirements.txt not found"
    exit 1
fi

# Test 4: Check environment template
echo ""
echo "🔧 Checking environment template..."
if [ -f ".env.example" ]; then
    required_vars=("TOKEN" "GEMINI_API_KEY" "DATABASE_PATH" "LOG_LEVEL")
    for var in "${required_vars[@]}"; do
        if grep -q "^$var=" .env.example; then
            print_status "$var variable found in .env.example"
        else
            print_error "$var variable missing from .env.example"
            exit 1
        fi
    done
else
    print_error ".env.example not found"
    exit 1
fi

# Test 5: Check setup script permissions
echo ""
echo "🔨 Checking setup script..."
if [ -x "deployment/setup_pi.sh" ]; then
    print_status "setup_pi.sh is executable"
else
    print_warning "setup_pi.sh is not executable - fixing..."
    chmod +x deployment/setup_pi.sh
    print_status "setup_pi.sh made executable"
fi

# Test 6: Validate systemd service
echo ""
echo "⚙️  Checking systemd service..."
if grep -q "sir-tim-bot" deployment/sir-tim-bot.service; then
    print_status "Service name found in systemd file"
else
    print_error "Service name not found in systemd file"
    exit 1
fi

if grep -q "ExecStart=" deployment/sir-tim-bot.service; then
    print_status "ExecStart directive found"
else
    print_error "ExecStart directive missing"
    exit 1
fi

# Test 7: Check GitHub Actions workflow
echo ""
echo "🚀 Checking GitHub Actions workflow..."
if grep -q "appleboy/ssh-action" .github/workflows/deploy.yml; then
    print_status "SSH action found in deployment workflow"
else
    print_error "SSH action missing from deployment workflow"
    exit 1
fi

required_secrets=("PI_HOST" "PI_USERNAME" "PI_SSH_KEY")
for secret in "${required_secrets[@]}"; do
    if grep -q "$secret" .github/workflows/deploy.yml; then
        print_status "$secret referenced in workflow"
    else
        print_error "$secret missing from workflow"
        exit 1
    fi
done

# Test 8: Try importing main modules (if in Python environment)
echo ""
echo "🔍 Testing module imports..."
python3 -c "
import sys
import os
sys.path.append('.')

try:
    from src.database import DatabaseManager
    print('✅ DatabaseManager import successful')
except ImportError as e:
    print(f'❌ DatabaseManager import failed: {e}')
    sys.exit(1)

try:
    from src.gemini_chat_handler import GeminiChatHandler
    print('✅ GeminiChatHandler import successful')
except ImportError as e:
    print(f'❌ GeminiChatHandler import failed: {e}')
    sys.exit(1)
"

echo ""
echo "🎉 All deployment tests passed!"
echo ""
print_status "Ready for deployment to Raspberry Pi"
echo ""
echo "Next steps:"
echo "1. Set up your Raspberry Pi using: deployment/setup_pi.sh"
echo "2. Configure GitHub secrets for automatic deployment"
echo "3. Push to main branch to trigger deployment"
echo ""
echo "For detailed instructions, see: deployment/README.md"
