# 🥬 Smart Vegetable POS System

An AI-powered Point of Sale (POS) system that automatically **detects vegetables** using a YOLOv8 computer vision model, **weighs them** using an Arduino-based load cell, and **generates bills** with PDF receipts — all through a single Tkinter GUI.

---

##  Repository Structure

```
Smart-Vegetable-POS/
│
├── Software_part/                  ← Development version (run via Python)
│   ├── camera_ui.py                ← Main application (entry point)
│   ├── weight_reader.py            ← Serial communication with Arduino
│   ├── database.py                 ← SQLite database operations
│   ├── receipt.py                  ← PDF receipt generation
│   ├── export.py                   ← CSV & Excel export
│   ├── camera.py                   ← Early prototype (CLI-based detection)
│   ├── final.py                    ← Early prototype (overlay UI on camera)
│   ├── check.py                    ← GPU/CUDA verification script
│   └── runs/detect/veg_yolov8_final/
│       ├── weights/best.pt         ← Trained YOLOv8 model
│       ├── args.yaml               ← Training configuration
│       └── results.csv             ← Training metrics
│
├── Portable_build/                 ← Portable EXE version (no Python needed)
│   ├── camera_ui.py                ← Main application (with settings screen)
│   ├── weight_reader.py            ← Serial communication with Arduino
│   ├── database.py                 ← SQLite database operations
│   ├── receipt.py                  ← PDF receipt generation
│   ├── export.py                   ← CSV & Excel export
│   ├── config.py                   ← Settings management (JSON-based)
│   ├── app_paths.py                ← Dynamic path resolution for EXE
│   ├── check_requirements.py       ← Dependency verification script
│   ├── VegetablePOS.spec           ← PyInstaller build specification
│   ├── best2.pt                    ← Trained YOLOv8 model
│   └── settings.json               ← User-configurable settings
│
├── requirements.txt
├── .gitignore
└── README.md
```

---

##  Module Descriptions

### Software_part (Development Version)

| File | Purpose |
|------|---------|
| `camera_ui.py` | **Main entry point.** Tkinter-based GUI that integrates camera feed, YOLO detection, weight reading, cart management, and billing. Uses a state machine with 4 states: `IDLE → DETECTING → LOCKED → SAVE_CONFIRM`. |
| `weight_reader.py` | Non-blocking serial reader that runs on a background thread. Reads raw weight values (in kg) from the Arduino via COM port. Supports smoothed (averaged) readings using a circular buffer. |
| `database.py` | Handles all SQLite operations. Creates `customers` and `transactions` tables. Saves complete sessions with auto-generated session IDs (e.g., `SES-20260306-143000`). |
| `receipt.py` | Generates professional PDF receipts using `fpdf2`. Includes customer info, itemized table with alternating row colors, grand total, and footer. Saves to a `receipts/` folder. |
| `export.py` | Exports transaction data to both CSV and Excel (`.xlsx`) files. Excel files include styled headers, formatted columns, and session total rows. Saves to a `sales_data/` folder. |

### Portable_build (EXE Version) — Additional Modules

| File | Purpose |
|------|---------|
| `config.py` | Manages user-configurable settings (COM port, baud rate, camera ID, model path) via a `settings.json` file. Auto-detects available COM ports and cameras. |
| `app_paths.py` | Resolves file paths dynamically. Detects whether the app is running as a Python script or as a frozen PyInstaller EXE, and adjusts paths accordingly. |
| `check_requirements.py` | Verifies all required Python packages are installed before building the EXE. |

---

##  Getting Started — Software_part (Development Version)

### Prerequisites

- **Python 3.10+** (tested with 3.10 and 3.11)
- **NVIDIA GPU** (recommended for faster YOLO inference, but CPU works too)
- **Arduino** connected via USB with a load cell + HX711 module
- **USB Camera** (external webcam)

### Step 1: Clone the Repository

```bash
git clone https://github.com/nasif3342028/Smart-Vegetable-POS.git
cd Smart-Vegetable-POS/Software_part
```

### Step 2: Create a Virtual Environment

```bash
python -m venv yolov8-env
```

**Activate it:**

- Windows: `yolov8-env\Scripts\activate`
- Linux/Mac: `source yolov8-env/bin/activate`

### Step 3: Install Dependencies

**For GPU (NVIDIA CUDA 11.8):**

```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
pip install ultralytics opencv-python pyserial fpdf2 openpyxl pillow
```

**For CPU only:**

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install ultralytics opencv-python pyserial fpdf2 openpyxl pillow
```

### Step 4: Verify GPU (Optional)

```bash
python check.py
```

Expected output (GPU):
```
Torch version: 2.x.x+cu118
CUDA available: True
GPU name: NVIDIA GeForce GTX/RTX xxxx
```

### Step 5: Configure `camera_ui.py`

Open `camera_ui.py` and update the configuration section at the top:

```python
# ================= CONFIG =================
MODEL_PATH = r"path\to\your\best.pt"    # Path to your trained YOLO model
CAMERA_ID = 1                            # Camera index (0 = built-in, 1 = external)
SERIAL_PORT = "COM5"                     # Arduino COM port
BAUDRATE = 9600                          # Must match Arduino code
MIN_VALID_WEIGHT = 0.005                 # Minimum weight threshold (kg)

PRICE_PER_KG = {
    "potato": 40.0,
    "tomato": 70.0,
    "onion": 65.0,
    "chili": 160.0,
    "cucumber": 130.0
}
# =========================================
```

**How to find your COM port:**
1. Open Device Manager (Windows)
2. Expand "Ports (COM & LPT)"
3. Look for "Arduino" or "USB-SERIAL" — note the COM number

### Step 6: Run the Application

```bash
python camera_ui.py
```

---

##  Application Workflow

### State Machine

The core detection logic uses a 4-state machine:

```
┌──────┐   weight > 0   ┌───────────┐   votes ≥ 3   ┌────────┐
│ IDLE │ ──────────────→ │ DETECTING │ ────────────→  │ LOCKED │
└──────┘                 └───────────┘                └────────┘
   ↑                         │                            │
   │    weight = 0           │                            │ weight = 0
   │←────────────────────────┘                            │ (auto-save)
   │                                                      ↓
   │                    2 sec delay                ┌──────────────┐
   │←──────────────────────────────────────────────│ SAVE_CONFIRM │
   │                                               └──────────────┘
```

1. **IDLE** — Waiting for item on scale. No detection running.
2. **DETECTING** — Weight detected. YOLO runs on each frame. Votes are counted.
3. **LOCKED** — Vegetable identified (≥3 votes). Weight is tracked. Display shows live price.
4. **SAVE_CONFIRM** — Item removed from scale → auto-saved to cart. Confirmation shown for 2 seconds.

### User Flow

```
Start Application
      │
      ▼
┌─────────────────┐
│  Customer Form  │  ← Enter name + 11-digit mobile number
│  (Name, Mobile) │
└────────┬────────┘
         │ Click "START BILLING"
         ▼
┌─────────────────┐
│   Main Screen   │  ← Camera feed + Live transaction + Cart
│                 │
│  Place veggie   │──→ YOLO detects + Load cell weighs
│  on scale       │
│                 │
│  Remove veggie  │──→ Auto-saves to cart
│  from scale     │
│                 │
│  Repeat...      │
│                 │
│  Click FINISH   │──→ Saves to DB + PDF + CSV + Excel
│  SESSION        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Session Summary │  ← Shows what was saved
│ + PDF Receipt   │  ← Auto-opens the PDF
└────────┬────────┘
         │
         ▼
   Back to Customer Form (ready for next customer)
```

---

##  Building the Portable EXE

### Step 1: Navigate to Portable_build

```bash
cd Smart-Vegetable-POS/Portable_build
```

### Step 2: Create Virtual Environment

```bash
python -m venv venv
venv\Scripts\activate
```

### Step 3: Install Dependencies (CPU-only for smaller EXE)

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install ultralytics opencv-python pyserial fpdf2 openpyxl pillow pyinstaller pyinstaller-hooks-contrib
```

### Step 4: Verify Requirements

```bash
python check_requirements.py
```

All packages should show `[OK]`.

### Step 5: Build the EXE

```bash
pyinstaller --noconfirm --clean --noconsole --name VegetablePOS ^
  --add-data "best2.pt;." ^
  --hidden-import app_paths ^
  --hidden-import weight_reader ^
  --hidden-import database ^
  --hidden-import receipt ^
  --hidden-import export ^
  --hidden-import config ^
  --hidden-import ultralytics ^
  --hidden-import cv2 ^
  --hidden-import torch ^
  --hidden-import PIL ^
  --hidden-import fpdf ^
  --hidden-import openpyxl ^
  --hidden-import serial ^
  --hidden-import serial.tools.list_ports ^
  camera_ui.py
```

### Step 6: Copy Model & Test

```bash
copy best2.pt dist\VegetablePOS\
cd dist\VegetablePOS
VegetablePOS.exe
```

> **Note:** First launch takes 30–60 seconds to extract and load all bundled libraries.

### Portable Folder Structure (After First Run)

```
VegetablePOS/
├── VegetablePOS.exe          ← Double-click to run
├── _internal/                ← Bundled Python + libraries (don't modify)
├── best2.pt                  ← YOLO model file
├── settings.json             ← Auto-created on first run
├── vegetable_pos.db          ← Auto-created SQLite database
├── receipts/                 ← Auto-created PDF receipts folder
└── sales_data/               ← Auto-created CSV + Excel exports
```

---

##  GUI Screens

### 1. Settings Screen (Portable Version Only)

Appears on first launch. Configure:
- **COM Port** — Select from auto-detected ports
- **Baud Rate** — Must match Arduino (default: 9600)
- **Camera ID** — Select from auto-detected cameras
- **YOLO Model** — Browse for `.pt` file

### 2. Customer Form

- Enter customer name and 11-digit mobile number
- Both fields are required

### 3. Main Billing Screen

| Section | Description |
|---------|-------------|
| **Camera Feed** (left) | Live video with YOLO bounding boxes |
| **Live Transaction** (right-top) | Status, detected item, weight, unit price, total |
| **Cart** (right-middle) | Table of all scanned items with delete option |
| **Price Configuration** (right-bottom) | Edit prices per kg on the fly |
| **Finish Session** (button) | Saves everything and generates receipt |

---

##  Database Schema

**SQLite** — File: `vegetable_pos.db`

```sql
-- Customers table
CREATE TABLE customers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    mobile      TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

-- Transactions table
CREATE TABLE transactions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id   INTEGER NOT NULL,
    session_id    TEXT NOT NULL,        -- e.g., "SES-20260306-143000"
    vegetable     TEXT NOT NULL,
    weight_kg     REAL NOT NULL,
    price_per_kg  REAL NOT NULL,
    total_price   REAL NOT NULL,
    created_at    TEXT NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers(id)
);
```

---

##  Output Files

| Output | Format | Location | Description |
|--------|--------|----------|-------------|
| Database | `.db` | Same as script/exe | All customer and transaction records |
| Receipt | `.pdf` | `receipts/` folder | Per-session itemized receipt |
| Sales Log | `.csv` | `sales_data/` folder | Append-only cumulative log |
| Sales Log | `.xlsx` | `sales_data/` folder | Formatted Excel with styled headers |

---

##  Configuration Reference

### Software_part — Hardcoded in `camera_ui.py`

| Parameter | Default | Description |
|-----------|---------|-------------|
| `MODEL_PATH` | *(must set)* | Full path to `best.pt` |
| `CAMERA_ID` | `1` | Camera index |
| `SERIAL_PORT` | "COM5" | Arduino COM port |
| `BAUDRATE` | `9600` | Serial baud rate |
| `MIN_VALID_WEIGHT` | `0.005` | Ignore weight below this (kg) |
| `MAX_DETECTION_FRAMES` | `10` | Max frames before forcing a decision |
| `MIN_VOTES_TO_LOCK` | `3` | Min votes to lock a detection |
| `SAVE_CONFIRMATION_MS` | `2000` | Confirmation display duration (ms) |

### Portable_build — Stored in `settings.json`

Same parameters but user-configurable via the Settings screen GUI. Saved/loaded automatically.

---

##  Hardware Requirements

| Component | Purpose |
|-----------|---------|
| Arduino (Uno/Nano) | Microcontroller for weight reading |
| HX711 Load Cell Amplifier | Amplifies load cell signal |
| Load Cell (5kg/10kg) | Measures weight of vegetables |
| USB Camera | Live video feed for YOLO detection |
| USB Cables | Connect Arduino + Camera to PC |

> The Arduino must send raw weight values (in kg) as plain numbers over serial, one per line. Example: `0.680\n`

---

##  Troubleshooting

| Problem | Solution |
|---------|----------|
| "YOLO Model file not found" | Update `MODEL_PATH` to the correct path of your `best.pt` |
| "Could not open serial port" | Check COM port in Device Manager. Make sure Arduino is plugged in. |
| "Camera could not be opened" | Try `CAMERA_ID = 0` instead of `1`. Ensure no other app is using the camera. |
| Weight reads 0 always | Check Arduino serial output with Serial Monitor first. Verify baud rate matches. |
| EXE opens and closes instantly | Rebuild with `--console` instead of `--noconsole` to see the error. |
| EXE takes too long to start | Normal on first launch (30–60 sec). Subsequent launches are faster. |

---

##  Team Members

- **Sami Akhtar Meer (22002117):** Hardware Implementation and 3D structure design in TINKERCAD, Physical enclosure prototyping and mechanical assembly, Component procurement, testing, and quality assurance, Hardware troubleshooting and calibration optimization.
- **Mehrab Jayen (220021215):** Dataset management, data annotation, and data augmentation, Image collection from multiple sources and lighting conditions, Roboflow-based annotation workflow and quality control, Data augmentation techniques (rotation, scaling, brightness adjustment), Dataset versioning and split management (train/validation/test).
- **Faizun Nasreen Linta (220021317):** Dataset management, data annotation, and data augmentation, Bounding box precision verification and annotation validation, Class balance analysis and augmentation strategy planning, Dataset documentation and metadata management, Cross-validation of annotated samples for consistency.
- **Nasif Fuad (220021334):** Implementing GUI and developing portability via .exe file, Tkinter GUI design with live camera feed integration, Cart-based billing logic and session management system, PyInstaller configuration for portable executable packaging, CSV/Excel export functionality and PDF receipt generation.
- **Tasnia Nabiha (220021336):** Training YOLOv8 model and integration of Arduino, load cell, and Python codes, YOLOv8 hyperparameter tuning and model optimization, Serial communication protocol between Arduino and Python, Real-time synchronization of detection and weight measurement, System integration testing and performance benchmarking.

---

##  License

This project was developed as a university final year project.
