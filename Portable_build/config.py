import json
import os
import serial.tools.list_ports
from app_paths import BASE_DIR, RESOURCE_DIR


CONFIG_PATH = os.path.join(BASE_DIR, "settings.json")

# Look for best2.pt
DEFAULT_MODEL = os.path.join(RESOURCE_DIR, "best2.pt")
if not os.path.exists(DEFAULT_MODEL):
    DEFAULT_MODEL = os.path.join(BASE_DIR, "best2.pt")
if not os.path.exists(DEFAULT_MODEL):
    DEFAULT_MODEL = ""

DEFAULT_SETTINGS = {
    "serial_port": "COM5",
    "baudrate": 9600,
    "camera_id": 1,
    "model_path": DEFAULT_MODEL,
    "min_valid_weight": 0.002,
    "max_detection_frames": 10,
    "min_votes_to_lock": 3,
    "save_confirmation_ms": 2000
}


class Config:

    def __init__(self, config_path=CONFIG_PATH):
        self.config_path = config_path
        self.settings = DEFAULT_SETTINGS.copy()
        self.load()

    def load(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    saved = json.load(f)
                for key in DEFAULT_SETTINGS:
                    if key in saved:
                        self.settings[key] = saved[key]
                print(f"[CONFIG] Loaded settings from: {self.config_path}")
            except Exception as e:
                print(f"[CONFIG] Failed to load settings: {e}. Using defaults.")
        else:
            print("[CONFIG] No config file found. Using defaults.")

    def save(self):
        try:
            with open(self.config_path, "w") as f:
                json.dump(self.settings, f, indent=4)
            print(f"[CONFIG] Settings saved to: {self.config_path}")
        except Exception as e:
            print(f"[CONFIG] Failed to save settings: {e}")
            raise RuntimeError(f"Failed to save settings: {e}")

    def get(self, key):
        return self.settings.get(key, DEFAULT_SETTINGS.get(key))

    def set(self, key, value):
        self.settings[key] = value

    def is_configured(self):
        model_path = self.settings.get("model_path", "")
        return model_path and os.path.exists(model_path)

    @staticmethod
    def get_available_ports():
        ports = serial.tools.list_ports.comports()
        port_list = []
        for port in ports:
            port_list.append({
                "device": port.device,
                "description": port.description
            })
        return port_list

    @staticmethod
    def get_available_cameras(max_check=5):
        import cv2
        available = []
        for i in range(max_check):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                available.append(i)
                cap.release()
        return available

    @staticmethod
    def find_model_files(search_dir=None):
        if search_dir is None:
            search_dir = BASE_DIR
        pt_files = []
        for root, dirs, files in os.walk(search_dir):
            for file in files:
                if file.endswith(".pt"):
                    pt_files.append(os.path.join(root, file))
        return pt_files