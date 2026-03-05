import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk
from ultralytics import YOLO
import cv2
import os
import sys
from collections import Counter
from app_paths import BASE_DIR, RESOURCE_DIR
from weight_reader import WeightReader
from database import Database
from receipt import ReceiptGenerator
from export import DataExporter
from config import Config


PRICE_PER_KG = {
    "potato": 40.0,
    "tomato": 70.0,
    "onion": 65.0,
    "chili": 160.0,
    "cucumber": 130.0
}


class SmartScaleApp:
    def __init__(self, window, window_title):
        self.window = window
        self.window.title(window_title)
        self.window.geometry("1200x700")
        self.window.configure(bg="#1e1e1e")

        self.current_prices = PRICE_PER_KG.copy()
        self.detected_veg = None
        self.current_weight = 0.0
        self.running = True

        self.session_active = False
        self.customer_info = {"name": "", "mobile": ""}

        self.state = "IDLE"
        self.locked_vegetable = None
        self.last_stable_weight = 0.0
        self.detection_votes = Counter()
        self.detection_frame_count = 0
        self.cart_items = []

        self.reader = None
        self.model = None
        self.cap = None
        self.class_names = {}

        self.config = Config()

        try:
            self.db = Database()
        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to initialize database:\n{e}")
            self.window.destroy()
            return

        try:
            self.receipt_gen = ReceiptGenerator()
        except Exception as e:
            messagebox.showerror("Receipt Error", f"Failed to initialize receipt generator:\n{e}")
            self.window.destroy()
            return

        try:
            self.exporter = DataExporter()
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to initialize data exporter:\n{e}")
            self.window.destroy()
            return

        self.create_gui()

        if self.config.is_configured():
            if self.init_hardware():
                self.show_customer_form()
            else:
                self.show_settings_screen()
        else:
            self.show_settings_screen()

        self.update_loop()

    # ──────────────────────────────────────────────────────────
    # GUI CREATION
    # ──────────────────────────────────────────────────────────

    def create_gui(self):
        self.master_frame = tk.Frame(self.window, bg="#1e1e1e")
        self.master_frame.pack(fill=tk.BOTH, expand=True)

    # ──────────────────────────────────────────────────────────
    # SETTINGS SCREEN
    # ──────────────────────────────────────────────────────────

    def show_settings_screen(self):
        for widget in self.master_frame.winfo_children():
            widget.destroy()
        self.session_active = False
        self.build_settings_screen()

    def build_settings_screen(self):
        settings_frame = tk.Frame(self.master_frame, bg="#1e1e1e")
        settings_frame.pack(fill=tk.BOTH, expand=True)

        center = tk.Frame(settings_frame, bg="#252526", bd=2, relief="ridge")
        center.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(center, text="SMART VEGETABLE POS",
                 font=("Segoe UI", 24, "bold"), bg="#252526", fg="#00ffcc",
                 padx=40, pady=15).pack()

        tk.Label(center, text="System Configuration",
                 font=("Segoe UI", 14), bg="#252526", fg="#aaaaaa").pack(pady=(0, 20))

        # COM PORT
        port_frame = tk.Frame(center, bg="#252526")
        port_frame.pack(fill=tk.X, padx=40, pady=8)

        tk.Label(port_frame, text="Serial Port (COM):", font=("Segoe UI", 12),
                 bg="#252526", fg="white", anchor="w").pack(fill=tk.X)

        port_select_frame = tk.Frame(port_frame, bg="#252526")
        port_select_frame.pack(fill=tk.X, pady=(5, 0))

        available_ports = Config.get_available_ports()
        port_names = [f"{p['device']} - {p['description']}" for p in available_ports]
        port_devices = [p["device"] for p in available_ports]

        if not port_names:
            port_names = ["No ports found"]
            port_devices = [""]

        self.combo_port = ttk.Combobox(port_select_frame, values=port_names,
                                        font=("Consolas", 12), state="readonly", width=35)
        self.combo_port.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.available_port_devices = port_devices

        current_port = self.config.get("serial_port")
        for i, device in enumerate(port_devices):
            if device == current_port:
                self.combo_port.current(i)
                break
        else:
            if port_devices:
                self.combo_port.current(0)

        btn_refresh_ports = tk.Button(port_select_frame, text="REFRESH",
                                      font=("Segoe UI", 9, "bold"),
                                      bg="#444444", fg="white", relief="flat",
                                      command=self.refresh_ports)
        btn_refresh_ports.pack(side=tk.LEFT, padx=(10, 0))

        # BAUD RATE
        baud_frame = tk.Frame(center, bg="#252526")
        baud_frame.pack(fill=tk.X, padx=40, pady=8)

        tk.Label(baud_frame, text="Baud Rate:", font=("Segoe UI", 12),
                 bg="#252526", fg="white", anchor="w").pack(fill=tk.X)

        baud_options = ["9600", "14400", "19200", "38400", "57600", "115200"]
        self.combo_baud = ttk.Combobox(baud_frame, values=baud_options,
                                        font=("Consolas", 12), state="readonly", width=35)
        self.combo_baud.pack(fill=tk.X, pady=(5, 0))

        current_baud = str(self.config.get("baudrate"))
        if current_baud in baud_options:
            self.combo_baud.current(baud_options.index(current_baud))
        else:
            self.combo_baud.current(0)

        # CAMERA ID
        cam_frame = tk.Frame(center, bg="#252526")
        cam_frame.pack(fill=tk.X, padx=40, pady=8)

        tk.Label(cam_frame, text="Camera ID:", font=("Segoe UI", 12),
                 bg="#252526", fg="white", anchor="w").pack(fill=tk.X)

        cam_select_frame = tk.Frame(cam_frame, bg="#252526")
        cam_select_frame.pack(fill=tk.X, pady=(5, 0))

        available_cams = Config.get_available_cameras()
        cam_options = [str(c) for c in available_cams] if available_cams else ["0"]

        self.combo_camera = ttk.Combobox(cam_select_frame, values=cam_options,
                                          font=("Consolas", 12), state="readonly", width=35)
        self.combo_camera.pack(side=tk.LEFT, fill=tk.X, expand=True)

        current_cam = str(self.config.get("camera_id"))
        if current_cam in cam_options:
            self.combo_camera.current(cam_options.index(current_cam))
        else:
            self.combo_camera.current(0)

        # MODEL FILE
        model_frame = tk.Frame(center, bg="#252526")
        model_frame.pack(fill=tk.X, padx=40, pady=8)

        tk.Label(model_frame, text="YOLO Model File (.pt):", font=("Segoe UI", 12),
                 bg="#252526", fg="white", anchor="w").pack(fill=tk.X)

        model_select_frame = tk.Frame(model_frame, bg="#252526")
        model_select_frame.pack(fill=tk.X, pady=(5, 0))

        self.entry_model = tk.Entry(model_select_frame, font=("Consolas", 11), width=30)
        self.entry_model.pack(side=tk.LEFT, fill=tk.X, expand=True)

        current_model = self.config.get("model_path")
        if current_model:
            self.entry_model.insert(0, current_model)

        btn_browse = tk.Button(model_select_frame, text="BROWSE",
                               font=("Segoe UI", 9, "bold"),
                               bg="#444444", fg="white", relief="flat",
                               command=self.browse_model)
        btn_browse.pack(side=tk.LEFT, padx=(10, 0))

        self.lbl_model_info = tk.Label(center, text="", font=("Segoe UI", 9),
                                        bg="#252526", fg="#aaaaaa")
        self.lbl_model_info.pack(pady=(5, 0))

        if current_model and os.path.exists(current_model):
            size_mb = os.path.getsize(current_model) / (1024 * 1024)
            self.lbl_model_info.config(text=f"Model size: {size_mb:.1f} MB", fg="#00ff00")

        self.lbl_settings_error = tk.Label(center, text="", font=("Segoe UI", 10),
                                            bg="#252526", fg="#ff4444")
        self.lbl_settings_error.pack(pady=(10, 0))

        btn_save = tk.Button(center, text="SAVE AND CONTINUE",
                             font=("Segoe UI", 14, "bold"),
                             bg="#007acc", fg="white", relief="flat",
                             cursor="hand2", padx=30, pady=10,
                             command=self.save_settings)
        btn_save.pack(pady=25)

    def refresh_ports(self):
        available_ports = Config.get_available_ports()
        port_names = [f"{p['device']} - {p['description']}" for p in available_ports]
        port_devices = [p["device"] for p in available_ports]

        if not port_names:
            port_names = ["No ports found"]
            port_devices = [""]

        self.combo_port.config(values=port_names)
        self.available_port_devices = port_devices

        if port_devices:
            self.combo_port.current(0)

    def browse_model(self):
        filepath = filedialog.askopenfilename(
            title="Select YOLO Model File",
            filetypes=[("PyTorch Model", "*.pt"), ("All Files", "*.*")]
        )
        if filepath:
            self.entry_model.delete(0, tk.END)
            self.entry_model.insert(0, filepath)
            size_mb = os.path.getsize(filepath) / (1024 * 1024)
            self.lbl_model_info.config(text=f"Model size: {size_mb:.1f} MB", fg="#00ff00")

    def save_settings(self):
        port_index = self.combo_port.current()
        if port_index < 0 or not self.available_port_devices[port_index]:
            self.lbl_settings_error.config(text="Please select a valid COM port.")
            return

        selected_port = self.available_port_devices[port_index]

        baud_str = self.combo_baud.get()
        if not baud_str:
            self.lbl_settings_error.config(text="Please select a baud rate.")
            return
        selected_baud = int(baud_str)

        cam_str = self.combo_camera.get()
        if not cam_str:
            self.lbl_settings_error.config(text="Please select a camera.")
            return
        selected_camera = int(cam_str)

        model_path = self.entry_model.get().strip()
        if not model_path:
            self.lbl_settings_error.config(text="Please select a YOLO model file.")
            return
        if not os.path.exists(model_path):
            self.lbl_settings_error.config(text="Model file not found. Please browse again.")
            return
        if not model_path.endswith(".pt"):
            self.lbl_settings_error.config(text="Model file must be a .pt file.")
            return

        self.config.set("serial_port", selected_port)
        self.config.set("baudrate", selected_baud)
        self.config.set("camera_id", selected_camera)
        self.config.set("model_path", model_path)

        try:
            self.config.save()
        except RuntimeError as e:
            self.lbl_settings_error.config(text=f"Failed to save: {e}")
            return

        if self.init_hardware():
            self.show_customer_form()
        else:
            self.lbl_settings_error.config(text="Hardware initialization failed. Check settings.")

    # ──────────────────────────────────────────────────────────
    # CUSTOMER FORM
    # ──────────────────────────────────────────────────────────

    def show_customer_form(self):
        for widget in self.master_frame.winfo_children():
            widget.destroy()
        self.session_active = False
        self.build_customer_form()

    def build_customer_form(self):
        self.customer_form_frame = tk.Frame(self.master_frame, bg="#1e1e1e")
        self.customer_form_frame.pack(fill=tk.BOTH, expand=True)

        center = tk.Frame(self.customer_form_frame, bg="#252526", bd=2, relief="ridge")
        center.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(center, text="SMART VEGETABLE POS",
                 font=("Segoe UI", 24, "bold"), bg="#252526", fg="#00ffcc",
                 padx=40, pady=20).pack()

        tk.Label(center, text="Enter Customer Details to Begin",
                 font=("Segoe UI", 12), bg="#252526", fg="#aaaaaa").pack(pady=(0, 20))

        name_frame = tk.Frame(center, bg="#252526")
        name_frame.pack(fill=tk.X, padx=40, pady=10)
        tk.Label(name_frame, text="Customer Name:", font=("Segoe UI", 12),
                 bg="#252526", fg="white", anchor="w").pack(fill=tk.X)
        self.entry_name = tk.Entry(name_frame, font=("Consolas", 14), width=30)
        self.entry_name.pack(fill=tk.X, pady=(5, 0))

        mobile_frame = tk.Frame(center, bg="#252526")
        mobile_frame.pack(fill=tk.X, padx=40, pady=10)
        tk.Label(mobile_frame, text="Mobile Number:", font=("Segoe UI", 12),
                 bg="#252526", fg="white", anchor="w").pack(fill=tk.X)
        self.entry_mobile = tk.Entry(mobile_frame, font=("Consolas", 14), width=30)
        self.entry_mobile.pack(fill=tk.X, pady=(5, 0))

        self.lbl_form_error = tk.Label(center, text="", font=("Segoe UI", 10),
                                       bg="#252526", fg="#ff4444")
        self.lbl_form_error.pack(pady=(10, 0))

        btn_frame = tk.Frame(center, bg="#252526")
        btn_frame.pack(pady=25)

        btn_start = tk.Button(btn_frame, text="START BILLING",
                              font=("Segoe UI", 14, "bold"),
                              bg="#007acc", fg="white", relief="flat",
                              cursor="hand2", padx=30, pady=10,
                              command=self.start_session)
        btn_start.pack(side=tk.LEFT, padx=10)

        btn_settings = tk.Button(btn_frame, text="SETTINGS",
                                 font=("Segoe UI", 14, "bold"),
                                 bg="#444444", fg="white", relief="flat",
                                 cursor="hand2", padx=30, pady=10,
                                 command=self.show_settings_screen)
        btn_settings.pack(side=tk.LEFT, padx=10)

        model_name = os.path.basename(self.config.get("model_path")) if self.config.get("model_path") else "Not set"
        config_text = (f"Port: {self.config.get('serial_port')}  |  "
                       f"Camera: {self.config.get('camera_id')}  |  "
                       f"Model: {model_name}")
        tk.Label(center, text=config_text, font=("Segoe UI", 9),
                 bg="#252526", fg="#666666").pack(pady=(0, 15))

        self.entry_name.bind("<Return>", lambda e: self.entry_mobile.focus())
        self.entry_mobile.bind("<Return>", lambda e: self.start_session())
        self.entry_name.focus_set()

    # ──────────────────────────────────────────────────────────
    # MAIN SCREEN
    # ──────────────────────────────────────────────────────────

    def build_main_screen(self):
        self.main_screen_frame = tk.Frame(self.master_frame, bg="#1e1e1e")
        self.main_screen_frame.pack(fill=tk.BOTH, expand=True)

        header = tk.Frame(self.main_screen_frame, bg="#2d2d2d", height=60)
        header.pack(fill=tk.X)

        header_left = tk.Frame(header, bg="#2d2d2d")
        header_left.pack(side=tk.LEFT, padx=20)
        tk.Label(header_left, text="SMART VEGETABLE POS SYSTEM",
                 font=("Segoe UI", 16, "bold"), bg="#2d2d2d", fg="#00ffcc").pack(anchor="w")

        header_right = tk.Frame(header, bg="#2d2d2d")
        header_right.pack(side=tk.RIGHT, padx=20)
        customer_text = f"Customer: {self.customer_info['name']}  |  Mobile: {self.customer_info['mobile']}"
        tk.Label(header_right, text=customer_text,
                 font=("Segoe UI", 11), bg="#2d2d2d", fg="#ffffff").pack(anchor="e", pady=5)

        content = tk.Frame(self.main_screen_frame, bg="#1e1e1e")
        content.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        self.cam_frame = tk.Frame(content, bg="black", width=640, height=480)
        self.cam_frame.pack(side=tk.LEFT, padx=10)
        self.video_label = tk.Label(self.cam_frame, bg="black")
        self.video_label.pack()

        right_panel = tk.Frame(content, bg="#252526", width=400)
        right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)

        bill_frame = tk.LabelFrame(right_panel, text=" LIVE TRANSACTION ",
                                   font=("Segoe UI", 12, "bold"), bg="#252526", fg="white", bd=2)
        bill_frame.pack(fill=tk.X, pady=5, padx=10)

        self.lbl_status = self.create_stat_row(bill_frame, "STATUS:", "PLACE ITEM ON SCALE", "#ffaa00")
        self.lbl_item = self.create_stat_row(bill_frame, "DETECTED ITEM:", "---", "#00ffcc")
        self.lbl_weight = self.create_stat_row(bill_frame, "WEIGHT (g):", "0", "#ffffff")
        self.lbl_price = self.create_stat_row(bill_frame, "UNIT PRICE:", "0.00 BDT", "#aaaaaa")

        tk.Label(bill_frame, text="TOTAL PAYABLE", font=("Segoe UI", 10),
                 bg="#252526", fg="#aaaaaa").pack(pady=(10, 0))
        self.lbl_total = tk.Label(bill_frame, text="0.00 BDT",
                                  font=("Segoe UI", 30, "bold"), bg="#252526", fg="#555555")
        self.lbl_total.pack(pady=(0, 10))

        cart_frame = tk.LabelFrame(right_panel, text=" CART ",
                                   font=("Segoe UI", 12, "bold"), bg="#252526", fg="white", bd=2)
        cart_frame.pack(fill=tk.BOTH, expand=True, pady=5, padx=10)

        columns = ("no", "item", "weight", "rate", "total")
        self.cart_tree = ttk.Treeview(cart_frame, columns=columns, show="headings", height=5)
        self.cart_tree.heading("no", text="#")
        self.cart_tree.heading("item", text="Item")
        self.cart_tree.heading("weight", text="Weight")
        self.cart_tree.heading("rate", text="Rate")
        self.cart_tree.heading("total", text="Total")

        self.cart_tree.column("no", width=30, anchor="center")
        self.cart_tree.column("item", width=80, anchor="center")
        self.cart_tree.column("weight", width=80, anchor="center")
        self.cart_tree.column("rate", width=70, anchor="center")
        self.cart_tree.column("total", width=90, anchor="center")

        self.cart_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        cart_scrollbar = ttk.Scrollbar(cart_frame, orient="vertical", command=self.cart_tree.yview)
        self.cart_tree.configure(yscrollcommand=cart_scrollbar.set)
        cart_scrollbar.pack(side="right", fill="y")

        self.lbl_grand_total = tk.Label(cart_frame, text="GRAND TOTAL: 0.00 BDT",
                                        font=("Consolas", 14, "bold"), bg="#252526", fg="#00ff00")
        self.lbl_grand_total.pack(pady=5)

        btn_delete = tk.Button(cart_frame, text="DELETE SELECTED ITEM",
                               font=("Segoe UI", 10, "bold"),
                               bg="#cc3333", fg="white", relief="flat",
                               cursor="hand2", command=self.delete_selected_item)
        btn_delete.pack(fill=tk.X, padx=5, pady=5)

        editor_frame = tk.LabelFrame(right_panel, text=" PRICE CONFIGURATION (BDT/KG) ",
                                     font=("Segoe UI", 12, "bold"), bg="#252526", fg="white", bd=2)
        editor_frame.pack(fill=tk.X, pady=5, padx=10)

        price_inner = tk.Frame(editor_frame, bg="#252526")
        price_inner.pack(fill=tk.X, padx=5, pady=5)

        self.price_inputs = {}
        col = 0
        row = 0
        for veg, price in self.current_prices.items():
            tk.Label(price_inner, text=veg.upper(), font=("Consolas", 10),
                     bg="#252526", fg="white", anchor="w").grid(row=row, column=col, padx=5, pady=2, sticky="w")
            ent = tk.Entry(price_inner, font=("Consolas", 10), width=7, justify='right')
            ent.insert(0, str(price))
            ent.grid(row=row, column=col + 1, padx=5, pady=2)
            self.price_inputs[veg] = ent
            row += 1
            if row >= 3:
                row = 0
                col += 2

        btn_update = tk.Button(editor_frame, text="UPDATE PRICES",
                               font=("Segoe UI", 10, "bold"),
                               bg="#007acc", fg="white", relief="flat",
                               cursor="hand2", command=self.update_prices)
        btn_update.pack(fill=tk.X, padx=5, pady=5)

        btn_finish = tk.Button(right_panel, text="FINISH SESSION",
                               font=("Segoe UI", 14, "bold"),
                               bg="#cc6600", fg="white", relief="flat",
                               cursor="hand2", padx=20, pady=10,
                               command=self.finish_session)
        btn_finish.pack(fill=tk.X, padx=10, pady=10)

    def create_stat_row(self, parent, label, value, color):
        frame = tk.Frame(parent, bg="#252526")
        frame.pack(fill=tk.X, padx=10, pady=2)
        tk.Label(frame, text=label, font=("Segoe UI", 12), bg="#252526", fg="#aaaaaa",
                 width=15, anchor="w").pack(side=tk.LEFT)
        lbl_val = tk.Label(frame, text=value, font=("Consolas", 14, "bold"), bg="#252526", fg=color)
        lbl_val.pack(side=tk.RIGHT)
        return lbl_val

    # ──────────────────────────────────────────────────────────
    # SESSION MANAGEMENT
    # ──────────────────────────────────────────────────────────

    def start_session(self):
        name = self.entry_name.get().strip()
        mobile = self.entry_mobile.get().strip()

        if not name:
            self.lbl_form_error.config(text="Please enter customer name.")
            self.entry_name.focus_set()
            return
        if not mobile:
            self.lbl_form_error.config(text="Please enter mobile number.")
            self.entry_mobile.focus_set()
            return
        if not mobile.isdigit() or len(mobile) != 11:
            self.lbl_form_error.config(text="Mobile number must be exactly 11 digits.")
            self.entry_mobile.focus_set()
            return

        self.customer_info = {"name": name, "mobile": mobile}

        self.cart_items = []
        self.state = "IDLE"
        self.locked_vegetable = None
        self.last_stable_weight = 0.0
        self.detection_votes.clear()
        self.detection_frame_count = 0
        self.detected_veg = None

        for widget in self.master_frame.winfo_children():
            widget.destroy()

        self.session_active = True
        self.build_main_screen()

    def finish_session(self):
        if not self.cart_items:
            result = messagebox.askyesno("Empty Cart",
                                         "The cart is empty. Are you sure you want to finish?")
            if not result:
                return

        save_result = None
        if self.cart_items:
            try:
                save_result = self.db.save_session(self.customer_info, self.cart_items)
            except RuntimeError as e:
                messagebox.showerror("Database Error", str(e))
                return

        receipt_path = None
        if save_result:
            try:
                receipt_path = self.receipt_gen.generate(
                    self.customer_info, self.cart_items, save_result["session_id"]
                )
            except Exception as e:
                messagebox.showwarning("Receipt Warning",
                                       f"Data saved but receipt generation failed:\n{e}")

        export_result = None
        if save_result:
            try:
                export_result = self.exporter.export_all(
                    self.customer_info, self.cart_items, save_result["session_id"]
                )
            except Exception as e:
                messagebox.showwarning("Export Warning",
                                       f"Data saved but export failed:\n{e}")

        summary = f"Customer: {self.customer_info['name']}\n"
        summary += f"Mobile: {self.customer_info['mobile']}\n\n"

        if save_result:
            summary += f"Session ID: {save_result['session_id']}\n"
            summary += f"Items Saved: {save_result['items_saved']}\n"
            summary += f"Grand Total: {save_result['grand_total']:.2f} BDT\n\n"
            summary += "[Database] Saved successfully.\n"

            if receipt_path:
                summary += "[Receipt] PDF generated.\n"
            else:
                summary += "[Receipt] Generation failed.\n"

            if export_result:
                if export_result["csv_success"]:
                    summary += "[CSV] Exported successfully.\n"
                else:
                    summary += "[CSV] Export failed.\n"
                if export_result["excel_success"]:
                    summary += "[Excel] Exported successfully.\n"
                else:
                    summary += "[Excel] Export failed.\n"
        else:
            summary += "No items to save.\n"

        messagebox.showinfo("Session Complete", summary)

        if receipt_path and os.path.exists(receipt_path):
            os.startfile(receipt_path)

        self.session_active = False
        self.show_customer_form()

    # ──────────────────────────────────────────────────────────
    # CART MANAGEMENT
    # ──────────────────────────────────────────────────────────

    def delete_selected_item(self):
        selected = self.cart_tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select an item to delete.")
            return

        item_index = self.cart_tree.index(selected[0])
        removed = self.cart_items.pop(item_index)
        self.cart_tree.delete(selected[0])

        for i, tree_item in enumerate(self.cart_tree.get_children()):
            self.cart_tree.set(tree_item, "no", i + 1)

        self.update_grand_total()

        messagebox.showinfo("Deleted",
                            f"Removed: {removed['vegetable'].upper()} "
                            f"{removed['weight_kg']:.3f}kg "
                            f"{removed['total']:.2f} BDT")

    # ──────────────────────────────────────────────────────────
    # HARDWARE
    # ──────────────────────────────────────────────────────────

    def init_hardware(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        if self.reader is not None:
            self.reader.stop()
            self.reader = None

        serial_port = self.config.get("serial_port")
        baudrate = self.config.get("baudrate")
        try:
            self.reader = WeightReader(port=serial_port, baudrate=baudrate, buffer_size=3)
            self.reader.start()
            print(f"[HARDWARE] Weight reader connected on {serial_port} at {baudrate}")
        except Exception as e:
            messagebox.showerror("Error", f"Weight Reader Failed:\n{e}\n\nPort: {serial_port}")
            return False

        model_path = self.config.get("model_path")
        if not os.path.exists(model_path):
            messagebox.showerror("Error", f"YOLO Model file not found:\n{model_path}")
            return False
        try:
            self.model = YOLO(model_path)
            self.class_names = self.model.names
            print(f"[HARDWARE] YOLO model loaded: {model_path}")
            print(f"[HARDWARE] Classes: {self.class_names}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load YOLO model:\n{e}")
            return False

        camera_id = self.config.get("camera_id")
        self.cap = cv2.VideoCapture(camera_id)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        if not self.cap.isOpened():
            messagebox.showerror("Error", f"Camera {camera_id} could not be opened.")
            return False

        print(f"[HARDWARE] Camera {camera_id} opened successfully.")
        return True

    def update_prices(self):
        try:
            for veg, entry in self.price_inputs.items():
                new_price = float(entry.get())
                self.current_prices[veg] = new_price
            messagebox.showinfo("Success", "Prices updated successfully!")
        except ValueError:
            messagebox.showerror("Error", "Invalid price format. Please enter numbers only.")

    # ──────────────────────────────────────────────────────────
    # CORE LOOP
    # ──────────────────────────────────────────────────────────

    def update_loop(self):
        if not self.running:
            return

        if self.session_active and self.cap is not None:
            ret, frame = self.cap.read()
            if ret:
                raw = self.reader.get_weight(smoothed=True)
                self.current_weight = raw if raw and raw > self.config.get("min_valid_weight") else 0.0

                if self.state == "IDLE":
                    self.handle_idle(frame)
                elif self.state == "DETECTING":
                    self.handle_detecting(frame)
                elif self.state == "LOCKED":
                    self.handle_locked(frame)
                elif self.state == "SAVE_CONFIRM":
                    pass

                cv2image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(cv2image)
                imgtk = ImageTk.PhotoImage(image=img)
                self.video_label.imgtk = imgtk
                self.video_label.configure(image=imgtk)

        self.window.after(15, self.update_loop)

    # ──────────────────────────────────────────────────────────
    # STATE HANDLERS
    # ──────────────────────────────────────────────────────────

    def handle_idle(self, frame):
        if self.current_weight > 0:
            self.state = "DETECTING"
            self.detection_votes.clear()
            self.detection_frame_count = 0
            self.lbl_status.config(text="SCANNING...", fg="#00ffcc")
            return

        self.lbl_status.config(text="PLACE ITEM ON SCALE", fg="#ffaa00")
        self.lbl_item.config(text="---", fg="#555555")
        self.lbl_weight.config(text="0")
        self.lbl_price.config(text="0.00 BDT")
        self.lbl_total.config(text="0.00 BDT", fg="#555555")

    def handle_detecting(self, frame):
        if self.current_weight <= 0:
            self.state = "IDLE"
            self.detection_votes.clear()
            self.detection_frame_count = 0
            return

        results = self.model(frame, verbose=False, conf=0.6)
        self.detection_frame_count += 1

        if results[0].boxes:
            best_box = max(results[0].boxes, key=lambda b: float(b.conf[0]))
            cls_id = int(best_box.cls[0])
            detected = self.class_names[cls_id]
            self.detection_votes[detected] += 1

            x1, y1, x2, y2 = map(int, best_box.xyxy[0])
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

        max_frames = self.config.get("max_detection_frames")
        min_votes = self.config.get("min_votes_to_lock")

        if self.detection_votes:
            top_class, top_count = self.detection_votes.most_common(1)[0]
            if top_count >= min_votes:
                self.locked_vegetable = top_class
                self.last_stable_weight = self.current_weight
                self.state = "LOCKED"
                self.lbl_status.config(text="LOCKED: " + top_class.upper(), fg="#00ff00")
                return

        if self.detection_frame_count >= max_frames:
            if self.detection_votes:
                top_class, _ = self.detection_votes.most_common(1)[0]
                self.locked_vegetable = top_class
                self.last_stable_weight = self.current_weight
                self.state = "LOCKED"
                self.lbl_status.config(text="LOCKED: " + top_class.upper(), fg="#00ff00")
            else:
                self.state = "IDLE"
                self.detection_votes.clear()
                self.detection_frame_count = 0
            return

        self.lbl_status.config(text="SCANNING...", fg="#00ffcc")
        self.lbl_item.config(text="IDENTIFYING...", fg="#ffaa00")
        self.lbl_weight.config(text=f"{int(self.current_weight * 1000)}")
        self.lbl_price.config(text="--- BDT")
        self.lbl_total.config(text="--- BDT", fg="#ffaa00")

    def handle_locked(self, frame):
        if self.current_weight > 0:
            # FIXED: Only update stable weight if weight is STABLE or INCREASING
            if self.current_weight >= self.last_stable_weight * 0.95:
                self.last_stable_weight = self.current_weight

            unit_price = self.current_prices.get(self.locked_vegetable, 0.0)
            total_price = self.last_stable_weight * unit_price

            self.lbl_status.config(text="LOCKED: " + self.locked_vegetable.upper(), fg="#00ff00")
            self.lbl_item.config(text=self.locked_vegetable.upper(), fg="#00ffcc")
            self.lbl_weight.config(text=f"{int(self.last_stable_weight * 1000)}")
            self.lbl_price.config(text=f"{unit_price:.2f} BDT")
            self.lbl_total.config(text=f"{total_price:.2f} BDT", fg="#00ff00")
        else:
            self.auto_save_item()

    # ──────────────────────────────────────────────────────────
    # AUTO-SAVE
    # ──────────────────────────────────────────────────────────

    def auto_save_item(self):
        if not self.locked_vegetable or self.last_stable_weight <= 0:
            self.reset_to_idle()
            return

        unit_price = self.current_prices.get(self.locked_vegetable, 0.0)
        total_price = round(self.last_stable_weight * unit_price, 2)

        item = {
            "vegetable": self.locked_vegetable,
            "weight_kg": round(self.last_stable_weight, 3),
            "price_per_kg": unit_price,
            "total": total_price
        }

        self.cart_items.append(item)

        self.cart_tree.insert("", "end", values=(
            len(self.cart_items),
            item["vegetable"].upper(),
            f"{item['weight_kg']:.3f} kg",
            f"{item['price_per_kg']:.0f}/kg",
            f"{item['total']:.2f} BDT"
        ))

        self.update_grand_total()

        self.state = "SAVE_CONFIRM"
        confirm_text = (f"SAVED: {item['vegetable'].upper()} "
                        f"{item['weight_kg']:.3f}kg "
                        f"{item['total']:.2f} BDT")
        self.lbl_status.config(text=confirm_text, fg="#00ff00")
        self.lbl_item.config(text=item["vegetable"].upper(), fg="#00ff00")
        self.lbl_weight.config(text=f"{int(item['weight_kg'] * 1000)}")
        self.lbl_total.config(text=f"{item['total']:.2f} BDT", fg="#00ff00")

        save_confirm_ms = self.config.get("save_confirmation_ms")
        self.window.after(save_confirm_ms, self.reset_to_idle)

    def reset_to_idle(self):
        self.state = "IDLE"
        self.locked_vegetable = None
        self.last_stable_weight = 0.0
        self.detection_votes.clear()
        self.detection_frame_count = 0
        self.detected_veg = None

    def update_grand_total(self):
        total = sum(item["total"] for item in self.cart_items)
        self.lbl_grand_total.config(text=f"GRAND TOTAL: {total:.2f} BDT")

    # ──────────────────────────────────────────────────────────
    # CLEANUP
    # ──────────────────────────────────────────────────────────

    def on_closing(self):
        self.running = False
        if self.cap is not None:
            self.cap.release()
        if self.reader is not None:
            self.reader.stop()
        self.window.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = SmartScaleApp(root, "Vegetable POS System")
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()