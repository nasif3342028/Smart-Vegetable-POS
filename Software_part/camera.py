from ultralytics import YOLO
import cv2
import os
import time

from weight_reader import WeightReader

# ================= CONFIG =================
MODEL_PATH = r"E:\Project\Final\Software_part\runs\detect\veg_yolov8_final\weights\best.pt"

CAMERA_ID = 1
CONF_THRESHOLD = 0.6
IMG_SIZE = 640

SERIAL_PORT = "COM5"
BAUDRATE = 9600

# Thresholds
MIN_VALID_WEIGHT = 0.002  # Ignore readings below 2g (removes noise when empty)

# UI Layout (Right Side)
TEXT_X_POS = 420          # X position for right-side text (Screen is 640 wide)
TEXT_FONT = cv2.FONT_HERSHEY_SIMPLEX

PRICE_PER_KG = {
    "potato": 40,
    "tomato": 60,
    "onion": 50,
    "radish": 30,
    "chili": 120,
    "cucumber": 45
}
# =========================================

def main():
    # 1. Load YOLO
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError("❌ YOLO model not found")

    print("🧠 Loading YOLO model...")
    model = YOLO(MODEL_PATH)
    class_names = model.names
    
    # 2. Start Weight Reader
    print("🔌 Starting weight reader...")
    try:
        # Buffer size 3 for instant response
        reader = WeightReader(port=SERIAL_PORT, baudrate=BAUDRATE, buffer_size=3)
        reader.start()
        print(f"✅ Connected to {SERIAL_PORT}")
    except RuntimeError as e:
        print(f"\n{e}")
        return

    # 3. Open Camera
    cap = cv2.VideoCapture(CAMERA_ID)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    print("="*50)
    print("📷 VEGETABLE WEIGHING SYSTEM (Instant Mode)")
    print("="*50)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # --- STEP 1: DETECT OBJECT (YOLO) ---
        results = model(frame, conf=CONF_THRESHOLD, imgsz=IMG_SIZE, verbose=False)
        detected_vegetable = None

        if results[0].boxes:
            # Pick the object with highest confidence
            best_box = max(results[0].boxes, key=lambda b: float(b.conf[0]))
            cls_id = int(best_box.cls[0])
            detected_vegetable = class_names[cls_id]
            
            # Draw bounding box
            x1, y1, x2, y2 = map(int, best_box.xyxy[0])
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

        # --- STEP 2: GET WEIGHT ---
        raw_weight = reader.get_weight(smoothed=True)
        
        # Handle 'None' or negative noise
        if raw_weight is None: 
            raw_weight = 0.0
        
        # Zero suppression: if weight < 2g, treat as 0
        if raw_weight < MIN_VALID_WEIGHT:
            display_weight = 0.0
        else:
            display_weight = raw_weight

        # --- STEP 3: CALCULATE PRICE ---
        weight_grams = int(display_weight * 1000)
        price_text = "0.00"
        ui_color = (0, 255, 255) # Yellow (Idle/Scanning)

        if detected_vegetable and display_weight > 0:
            total_price = round(display_weight * PRICE_PER_KG[detected_vegetable], 2)
            price_text = f"{total_price}"
            ui_color = (0, 255, 0) # Green (Active)

        # --- STEP 4: DRAW UI (RIGHT SIDE) ---
        # We assume screen width 640. We start text at x=420.
        
        # Background box for text (Optional: improves readability)
        cv2.rectangle(frame, (TEXT_X_POS - 10, 20), (640, 180), (0, 0, 0), -1)
        cv2.rectangle(frame, (TEXT_X_POS - 10, 20), (640, 180), ui_color, 1)

        # Line 1: Item Name
        item_str = detected_vegetable.upper() if detected_vegetable else "WAITING..."
        cv2.putText(frame, f"{item_str}", (TEXT_X_POS, 60),
                   TEXT_FONT, 0.8, ui_color, 2)

        # Line 2: Weight
        cv2.putText(frame, f"{weight_grams} g", (TEXT_X_POS, 110),
                   TEXT_FONT, 1.0, (255, 255, 255), 2)

        # Line 3: Price
        cv2.putText(frame, f"{price_text} BDT", (TEXT_X_POS, 160),
                   TEXT_FONT, 1.0, ui_color, 2)

        # --- STEP 5: DISPLAY ---
        cv2.imshow("Vegetable Weighing System", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    reader.stop()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()