#!/usr/bin/env python3
"""
Script to install and configure an unfiltered model for Sir Tim the Timely.
This will download and configure the model for Ollama.
"""

import subprocess
import sys
import requests

MODEL_NAME = "tinyllama"  # TinyLlama (1.1B parameters) - will run on 1GB RAM Pi 3
OLLAMA_URL = "http://localhost:11434"

def check_ollama_running():
    """Check if Ollama server is running."""
    try:
        response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        if response.status_code == 200:
            return True
    except requests.exceptions.RequestException:
        pass
    return False

def check_model_exists():
    """Check if the model already exists in Ollama."""
    try:
        response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get("models", [])
            for model in models:
                if model.get("name") == MODEL_NAME:
                    return True
    except requests.exceptions.RequestException:
        pass
    return False

def pull_model():
    """Pull the model from Ollama."""
    print(f"Downloading the {MODEL_NAME} model... This might take a while depending on your internet connection.")
    print("This is a compact 1.1B parameter model that will actually run on a Raspberry Pi 3 with 1GB RAM.")
    print("TinyLlama is minimally aligned and will work with our unfiltered persona.")
    
    try:
        # Run the command and capture output
        result = subprocess.run(
            ["ollama", "pull", MODEL_NAME],
            capture_output=True,
            text=True,
            check=False
        )
        
        # Print the output
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr)
        
        if result.returncode == 0:
            print(f"\n✅ Successfully installed {MODEL_NAME} model!")
            return True
        else:
            print(f"\n❌ Failed to install {MODEL_NAME} model. Check the error messages above.")
            return False
            
    except Exception as e:
        print(f"Error pulling model: {e}")
        return False

def main():
    print("=" * 50)
    print("Sir Tim the Timely - Model Installer")
    print("=" * 50)
    
    if not check_ollama_running():
        print("❌ Ollama server is not running. Please start Ollama first.")
        print("   You can start it by running 'ollama serve' in another terminal.")
        return False
    
    print("✅ Ollama server is running.")
    
    if check_model_exists():
        print(f"✅ The {MODEL_NAME} model is already installed.")
        print("You're all set to use the improved model with Sir Tim!")
        return True
    
    success = pull_model()
    
    if success:
        print("\nTo use the new unfiltered model with Sir Tim:")
        print(f"1. The bot has been configured to use the {MODEL_NAME} model")
        print("2. WARNING: This model is unfiltered and will use profanity")
        print("3. Restart your bot with: python main.py")
        return True
    
    return False

if __name__ == "__main__":
    try:
        success = main()
        if not success:
            sys.exit(1)
    except KeyboardInterrupt:
        print("\nInstallation cancelled by user.")
        sys.exit(1)
