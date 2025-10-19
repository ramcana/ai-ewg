#!/usr/bin/env python3
"""Quick test of installed packages"""

print("Testing imports...")
print()

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
    print("✓ pyannote.audio installed")
except Exception as e:
    print(f"✗ pyannote.audio: {e}")

try:
    import fuzzywuzzy
    print("✓ fuzzywuzzy installed")
except Exception as e:
    print(f"✗ fuzzywuzzy: {e}")

try:
    import requests
    print("✓ requests installed")
except Exception as e:
    print(f"✗ requests: {e}")

try:
    import wikipediaapi
    print("✓ wikipedia-api installed")
except Exception as e:
    print(f"✗ wikipedia-api: {e}")

try:
    import spacy
    print("✓ spaCy installed (optional)")
except Exception as e:
    print("ℹ spaCy not installed (optional - use LLM method)")

print()
print("Core packages ready for AI enrichment!")
