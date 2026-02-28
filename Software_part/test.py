from ultralytics import YOLO
import cv2
import serial
import time
import numpy as np # Needed for the transparent overlay

# -------------------------------
# CONFIGURATION
# -------------------------------
PORT = "COM5"   
BAUD = 9600

PRICE_PER_KG = {
    "potato": 40, "tomato": 60, "onion": 50,
    "radish": 30, "chili": 120, "cucumber": 45
}

# UI Dimensions (Compact Box)
BOX_X, BOX_Y = 410, 20
BOX_W, BOX_H = 220, 210
TEXT_FONT = cv2.FONT_HERSHEY_SIMPLEX

# -------------------------------
# SETUP
# -------------------------------
try:
    ser = serial.Serial(PORT, BAUD, timeout=1)
    time.sleep(2)
except:
    ser = None
    print(f"Warning: Could not connect to {PORT}")

# CHANGE: Loading the model directly by filename
print("🧠 Loading YOLO model...")
model = YOLO("best(test-1).pt")

cap = cv2.VideoCapture(1)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

current_weight = 0.0

# -------------------------------
# MAIN LOOP
# -------------------------------
while True:
    ret, frame = cap.read()
    if not ret:
        print("Webcam not detected")
        break

    # ---- 1. YOLO Detection ----
    results = model(frame, conf=0.6, verbose=False)
    annotated_frame = results[0].plot()

    detected_vegetable = None
    if len(results[0].boxes) > 0:
        cls_id = int(results[0].boxes[0].cls[0])
        detected_vegetable = model.names[cls_id]

    # ---- 2. Read Weight (Negative Fix) ----
    try:
        if ser and ser.in_waiting:
            line = ser.readline().decode("utf-8").strip()
            raw_val = float(line)
            current_weight = 0.0 if raw_val < 0 else raw_val
    except:
        pass

    # ---- 3. Calculate Price & Logic ----
    weight_grams = round(current_weight * 1000)
    price_val = 0.00
    
    # Colors
    text_color = (255, 255, 255)       # White
    label_color = (200, 200, 200)      # Light Grey for labels
    accent_color = (0, 255, 255)       # Yellow (Idle)

    if detected_vegetable and current_weight > 0:
        if detected_vegetable in PRICE_PER_KG:
            price_val = round(current_weight * PRICE_PER_KG[detected_vegetable], 2)
            accent_color = (0, 255, 0) # Green (Active)

    # ---- 4. Draw UI (Compact Glass Card) ----
    
    # Define the Region of Interest (ROI) for the box
    overlay = annotated_frame.copy()
    
    # Draw the semi-transparent black box
    cv2.rectangle(overlay, (BOX_X, BOX_Y), (BOX_X + BOX_W, BOX_Y + BOX_H), (0, 0, 0), -1)
    
    # Apply transparency (0.6 opacity)
    alpha = 0.6
    cv2.addWeighted(overlay, alpha, annotated_frame, 1 - alpha, 0, annotated_frame)

    # Draw Accent Border (Left side of the card)
    cv2.line(annotated_frame, (BOX_X, BOX_Y), (BOX_X, BOX_Y + BOX_H), accent_color, 4)

    # --- TEXT CONTENT ---
    x_pad = BOX_X + 15
    item_str = detected_vegetable.upper() if detected_vegetable else "SCANNING..."

    # 1. Item
    cv2.putText(annotated_frame, "ITEM", (x_pad, BOX_Y + 30), TEXT_FONT, 0.4, label_color, 1)
    cv2.putText(annotated_frame, item_str, (x_pad, BOX_Y + 55), TEXT_FONT, 0.7, text_color, 2)

    # 2. Weight
    cv2.putText(annotated_frame, "WEIGHT", (x_pad, BOX_Y + 90), TEXT_FONT, 0.4, label_color, 1)
    cv2.putText(annotated_frame, f"{weight_grams} g", (x_pad, BOX_Y + 115), TEXT_FONT, 0.7, text_color, 2)
    # Tiny kg display
    cv2.putText(annotated_frame, f"({current_weight:.3f} kg)", (x_pad + 90, BOX_Y + 115), TEXT_FONT, 0.35, label_color, 1)

    # 3. Price (Bigger)
    cv2.putText(annotated_frame, "TOTAL PRICE (BDT)", (x_pad, BOX_Y + 155), TEXT_FONT, 0.4, label_color, 1)
    cv2.putText(annotated_frame, f"{price_val:.2f}", (x_pad, BOX_Y + 190), TEXT_FONT, 1.1, accent_color, 2)

    cv2.imshow("Vegetable Weighing System", annotated_frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
if ser:
    ser.close()
cv2.destroyAllWindows()