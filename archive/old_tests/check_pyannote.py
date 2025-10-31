try:
    import pyannote.audio
    print("✅ pyannote.audio is installed")
except ImportError:
    print("❌ pyannote.audio is NOT installed")
    print("Install with: pip install pyannote.audio")
