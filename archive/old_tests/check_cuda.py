import torch

print("="*50)
print("PyTorch CUDA Check")
print("="*50)
print(f"PyTorch version: {torch.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")

if torch.cuda.is_available():
    print(f"CUDA version: {torch.version.cuda}")
    print(f"GPU count: {torch.cuda.device_count()}")
    print(f"Current GPU: {torch.cuda.current_device()}")
    print(f"GPU name: {torch.cuda.get_device_name(0)}")
else:
    print("\n❌ CUDA is NOT available!")
    print("You need to install PyTorch with CUDA support:")
    print("\nRun this command:")
    print("pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121")
