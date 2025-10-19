import torch
from faster_whisper import WhisperModel

print("=" * 50)
print("GPU Verification")
print("=" * 50)
print()

print(f"CUDA Available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"GPU Name: {torch.cuda.get_device_name(0)}")
    print(f"CUDA Version: {torch.version.cuda}")
    print(f"GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB")
    print()
    print("Testing faster-whisper with GPU...")
    try:
        model = WhisperModel("tiny", device="cuda", compute_type="float16")
        print("✓ Faster-Whisper GPU initialization successful!")
        print()
        print("Your RTX 4080 is ready for transcription! 🚀")
    except Exception as e:
        print(f"✗ Error: {e}")
else:
    print("✗ CUDA not available - will use CPU (slower)")
    print("Check PyTorch installation")
