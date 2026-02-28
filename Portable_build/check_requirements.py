import sys

print(f"Python Version: {sys.version}\n")

packages = {
    "ultralytics": "YOLO Model",
    "cv2": "Camera / OpenCV",
    "serial": "Arduino Weight Reader",
    "PIL": "Image Processing",
    "fpdf": "PDF Receipt",
    "openpyxl": "Excel Export",
    "PyInstaller": "Packaging to EXE"
}

all_ok = True

for package, purpose in packages.items():
    try:
        __import__(package)
        print(f"  [OK]     {package:20s} ({purpose})")
    except ImportError:
        print(f"  [MISSING] {package:20s} ({purpose})")
        all_ok = False

print()
if all_ok:
    print("ALL REQUIREMENTS SATISFIED. Ready to build.")
else:
    print("SOME PACKAGES MISSING. Install them before building.")