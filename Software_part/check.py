import torch

def main():
    print("Torch version:", torch.__version__)
    print("CUDA available:", torch.cuda.is_available())

    if torch.cuda.is_available():
        print("GPU name:", torch.cuda.get_device_name(0))
        print("CUDA version (PyTorch):", torch.version.cuda)
        print("Number of GPUs:", torch.cuda.device_count())
    else:
        print("❌ GPU NOT detected by PyTorch")

if __name__ == "__main__":
    main()
