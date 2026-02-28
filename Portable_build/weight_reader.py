import serial
import threading
import time
from collections import deque


class WeightReader:
    """
    Non-blocking Arduino weight reader
    Expects RAW numeric weight per line (e.g. 0.68)
    """

    def __init__(self, port="COM5", baudrate=9600, buffer_size=10):
        self.port = port
        self.baudrate = baudrate
        self.buffer_size = buffer_size

        self.ser = None
        self.running = False
        self.thread = None

        self.weight_buffer = deque(maxlen=buffer_size)
        self.latest_weight = None

    def start(self):
        """Start serial reading thread"""
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            time.sleep(2)  # allow Arduino reset
        except serial.SerialException as e:
            raise RuntimeError(f"❌ Could not open serial port {self.port}: {e}")

        self.running = True
        self.thread = threading.Thread(target=self._read_loop, daemon=True)
        self.thread.start()

        print(f" Weight reader started on {self.port}")

    def _read_loop(self):
        """Internal serial read loop"""
        while self.running:
            try:
                line = self.ser.readline().decode().strip()

                if not line:
                    continue

                # Expect raw float only
                value = float(line)

                self.weight_buffer.append(value)
                self.latest_weight = value

            except ValueError:
                # Ignore malformed/non-numeric lines
                continue
            except Exception:
                continue

    def get_weight(self, smoothed=True):
        """Return current weight (kg)"""
        if not self.weight_buffer:
            return None

        if smoothed:
            return sum(self.weight_buffer) / len(self.weight_buffer)

        return self.latest_weight

    def clear_buffer(self):
        """Clear weight buffer (useful for fresh start)"""
        self.weight_buffer.clear()
        self.latest_weight = None

    def stop(self):
        """Stop reader cleanly"""
        self.running = False

        if self.thread:
            self.thread.join(timeout=1)

        if self.ser:
            self.ser.close()

        print(" Weight reader stopped")