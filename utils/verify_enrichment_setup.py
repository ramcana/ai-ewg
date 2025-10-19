#!/usr/bin/env python3
"""
Verify AI Enrichment System Setup
Checks all dependencies and configuration
"""

import sys
import os

def check_python_packages():
    """Check if required packages are installed"""
    required = [
        'pyannote.audio',
        'spacy',
        'requests',
        'fuzzywuzzy',
        'torch',
        'huggingface_hub'
    ]
    
    missing = []
    for package in required:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing.append(package)
    
    if missing:
        print(f"✗ Missing packages: {', '.join(missing)}")
        return False
    else:
        print("✓ Python packages installed")
        return True

def check_spacy_model():
    """Check if spaCy model is available"""
    try:
        import spacy
        nlp = spacy.load('en_core_web_lg')
        print("✓ spaCy model available")
        return True
    except:
        print("✗ spaCy model not found (run: python -m spacy download en_core_web_lg)")
        return False

def check_hf_token():
    """Check Hugging Face token"""
    token = os.getenv('HF_TOKEN')
    if not token:
        print("✗ Hugging Face token not set (set HF_TOKEN environment variable)")
        return False
    
    try:
        from huggingface_hub import login
        login(token=token)
        print("✓ Hugging Face token valid")
        return True
    except:
        print("✗ Hugging Face token invalid")
        return False

def check_ollama():
    """Check if Ollama is accessible"""
    import requests
    ollama_url = os.getenv('OLLAMA_URL', 'http://localhost:11434')
    
    try:
        response = requests.get(f"{ollama_url}/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get('models', [])
            if models:
                print(f"✓ Ollama accessible ({len(models)} models available)")
                return True
            else:
                print("⚠ Ollama accessible but no models installed (run: ollama pull mistral)")
                return False
        else:
            print("✗ Ollama not responding")
            return False
    except:
        print("✗ Ollama not accessible (is it running?)")
        return False

def check_gpu():
    """Check GPU availability"""
    try:
        import torch
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            print(f"✓ GPU available (CUDA): {gpu_name}")
            return True
        else:
            print("⚠ GPU not available (will use CPU - slower)")
            return False
    except:
        print("⚠ Could not check GPU status")
        return False

def check_env_vars():
    """Check environment variables"""
    required = ['HF_TOKEN']
    optional = ['OLLAMA_URL', 'OLLAMA_MODEL', 'DIARIZE_DEVICE', 'NEWSROOM_PATH']
    
    missing = [var for var in required if not os.getenv(var)]
    
    if missing:
        print(f"✗ Missing required env vars: {', '.join(missing)}")
        return False
    
    optional_missing = [var for var in optional if not os.getenv(var)]
    if optional_missing:
        print(f"⚠ Optional env vars not set: {', '.join(optional_missing)}")
    
    print("✓ Environment variables set")
    return True

def main():
    """Run all verification checks"""
    print("=" * 50)
    print("AI Enrichment System Setup Verification")
    print("=" * 50)
    print()
    
    checks = [
        check_python_packages,
        check_spacy_model,
        check_hf_token,
        check_ollama,
        check_gpu,
        check_env_vars
    ]
    
    results = [check() for check in checks]
    
    print()
    print("=" * 50)
    
    if all(results):
        print("✓ System ready for AI enrichment!")
        return 0
    else:
        print("✗ Setup incomplete - fix issues above")
        return 1

if __name__ == '__main__':
    sys.exit(main())
