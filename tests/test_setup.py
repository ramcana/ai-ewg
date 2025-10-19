#!/usr/bin/env python3
"""
Quick test of the enrichment setup with environment variables
"""

import os
import sys

# Load environment variables from .env file
def load_env_file():
    env_path = 'config/.env'
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value
                    print(f"Set {key}={value[:20]}...")

def test_imports():
    """Test basic imports"""
    print("\n=== Testing Imports ===")
    
    try:
        import torch
        print(f"✓ PyTorch: {torch.__version__}")
        print(f"  CUDA available: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"  GPU: {torch.cuda.get_device_name(0)}")
    except Exception as e:
        print(f"✗ PyTorch: {e}")

    try:
        import pyannote.audio
        print("✓ pyannote.audio available")
    except Exception as e:
        print(f"✗ pyannote.audio: {e}")

    try:
        import requests
        print("✓ requests available")
    except Exception as e:
        print(f"✗ requests: {e}")

    try:
        import fuzzywuzzy
        print("✓ fuzzywuzzy available")
    except Exception as e:
        print(f"✗ fuzzywuzzy: {e}")

    try:
        import spacy
        print("✓ spaCy available")
        try:
            nlp = spacy.load('en_core_web_lg')
            print("✓ spaCy model loaded")
        except:
            print("✗ spaCy model not found")
    except Exception as e:
        print(f"✗ spaCy: {e}")

def test_ollama():
    """Test Ollama connection"""
    print("\n=== Testing Ollama ===")
    
    try:
        import requests
        ollama_url = os.getenv('OLLAMA_URL', 'http://localhost:11434')
        
        response = requests.get(f"{ollama_url}/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get('models', [])
            print(f"✓ Ollama accessible ({len(models)} models)")
            for model in models[:3]:  # Show first 3 models
                print(f"  - {model.get('name', 'unknown')}")
        else:
            print("✗ Ollama not responding")
    except Exception as e:
        print(f"✗ Ollama error: {e}")

def test_hf_token():
    """Test Hugging Face token"""
    print("\n=== Testing HF Token ===")
    
    token = os.getenv('HF_TOKEN')
    if token:
        print(f"✓ HF_TOKEN set: {token[:10]}...")
        
        try:
            from huggingface_hub import login
            login(token=token)
            print("✓ HF token valid")
        except Exception as e:
            print(f"✗ HF token invalid: {e}")
    else:
        print("✗ HF_TOKEN not set")

def main():
    print("=== AI Enrichment Setup Test ===")
    
    # Load environment
    print("\n=== Loading Environment ===")
    load_env_file()
    
    # Run tests
    test_imports()
    test_ollama()
    test_hf_token()
    
    print("\n=== Summary ===")
    print("If you see ✓ for most items, you're ready to proceed!")
    print("If you see ✗ for critical items, install missing packages:")
    print("  pip install spacy fuzzywuzzy python-Levenshtein wikipediaapi")
    print("  python -m spacy download en_core_web_lg")

if __name__ == '__main__':
    main()