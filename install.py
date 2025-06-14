#!/usr/bin/env python3
"""
Sir Tim the Timely - Installation Script

This script guides users through the installation and setup process
for the Sir Tim the Timely Discord bot.
"""

import os
import sys
import subprocess
import shutil

def print_header():
    """Print a nice header for the installer."""
    print("\n" + "=" * 60)
    print("Sir Tim the Timely - Installation Helper".center(60))
    print("=" * 60)

def check_python_version():
    """Check if Python version is compatible."""
    print("\n📋 Checking Python version...")
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 9):
        print("❌ Error: Python 3.9+ is required. You are using Python {}.{}.{}".format(
            version.major, version.minor, version.micro))
        return False
    
    print(f"✅ Found Python {version.major}.{version.minor}.{version.micro}")
    return True

def install_requirements():
    """Install required packages from requirements.txt."""
    print("\n📦 Installing dependencies from requirements.txt...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)
        print("✅ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError:
        print("❌ Failed to install dependencies")
        return False

def setup_env_file():
    """Set up the .env file from the template."""
    print("\n🔧 Setting up environment configuration...")
    
    if os.path.exists(".env"):
        print("ℹ️ .env file already exists. Skipping.")
        return True
    
    if not os.path.exists(".env.example"):
        print("❌ .env.example not found. Cannot create .env file.")
        return False
    
    # Copy the example file
    shutil.copy(".env.example", ".env")
    print("✅ Created .env file from template")
    
    # Remind user to edit the file
    print("\nℹ️ Please edit the .env file with your Discord bot token and other settings.")
    print("ℹ️ At minimum, you need to provide a valid Discord TOKEN.")
    return True

def setup_database():
    """Run the database setup script."""
    print("\n🗄️ Setting up the database...")
    try:
        subprocess.run([sys.executable, "setup_database.py"], check=True)
        return True
    except subprocess.CalledProcessError:
        print("❌ Failed to set up the database")
        return False

def main():
    """Main function for the installation script."""
    print_header()
    
    if not check_python_version():
        sys.exit(1)
    
    if not install_requirements():
        sys.exit(1)
    
    if not setup_env_file():
        sys.exit(1)
    
    if not setup_database():
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("✅ Sir Tim the Timely installation completed successfully!".center(60))
    print("=" * 60)
    
    print("\n🚀 Run the bot with: python main.py")
    print("\n📚 See README.md for more information on commands and features.")

if __name__ == "__main__":
    main()
