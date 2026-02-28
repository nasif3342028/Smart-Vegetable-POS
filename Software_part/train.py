from ultralytics import YOLO
import torch
import gc
import os

def main():
    # -------------------------------------------------
    # 1. GPU & CUDA sanity
    # -------------------------------------------------
    torch.backends.cudnn.benchmark = True

    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        gc.collect()
        device = 0
        gpu_name = torch.cuda.get_device_name(0)
        vram = torch.cuda.get_device_properties(0).total_memory / 1e9
        print(f"✅ Using GPU: {gpu_name} ({vram:.2f} GB VRAM)")
    else:
        device = "cpu"
        print("⚠️ CUDA not available, using CPU")

    # -------------------------------------------------
    # 2. Dataset path (FIXED & VERIFIED)
    # -------------------------------------------------
    data_yaml_path = r"E:\Project\Final\Software_part\Vegetables-(Main)-1\data.yaml"

    if not os.path.exists(data_yaml_path):
        raise FileNotFoundError("❌ data.yaml not found. Check dataset path.")

    print(f"📄 Dataset config: {data_yaml_path}")

    # -------------------------------------------------
    # 3. Load model (YOLOv8 Nano – optimal for 4GB VRAM)
    # -------------------------------------------------
    print("🧠 Loading YOLOv8n model...")
    model = YOLO("yolov8n.pt")

    # -------------------------------------------------
    # 4. Training (STABLE + REALISTIC CONFIG)
    # -------------------------------------------------
    print("🚀 Starting training...")

    model.train(
        data=data_yaml_path,
        epochs=90,              # Enough for convergence on ~2k images
        imgsz=704,              # Better detail than 640, still VRAM-safe
        batch=8,                # SAFE for RTX 3050 (4GB)
        device=device,
        amp=True,               # Mixed precision → faster + lower VRAM

        workers=0,              # Windows-safe (avoid deadlocks)
        cache=False,

        # ---- Augmentation (minimal, realistic) ----
        mosaic=0.0,             # Disable (single object per image)
        mixup=0.0,              # Disable (hurts solid object detection)
        fliplr=0.5,             # Realistic
        flipud=0.0,             # Unrealistic for weighing platform

        optimizer="AdamW",      # Stable, fast convergence
        cos_lr=True,            # Smooth learning rate decay

        name="veg_yolov8_final",
        exist_ok=True,
        pretrained=True
    )

    print("🎉 Training complete!")
    print("📁 Best model saved in: runs/detect/veg_yolov8_final/weights/best.pt")

if __name__ == "__main__":
    main()


