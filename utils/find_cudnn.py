import os
import nvidia.cudnn

cudnn_path = os.path.dirname(nvidia.cudnn.__file__)
bin_path = os.path.join(cudnn_path, 'bin')

print(f"cuDNN installed at: {cudnn_path}")
print(f"DLL location: {bin_path}")

if os.path.exists(bin_path):
    dlls = [f for f in os.listdir(bin_path) if f.endswith('.dll')]
    print(f"\nFound {len(dlls)} DLLs:")
    for dll in dlls[:5]:
        print(f"  - {dll}")
else:
    print("Bin directory not found!")
