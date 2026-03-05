import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
from ultralytics import YOLO
import cv2
import os
from collections import Counter
from weight_reader import WeightReader
from database import Database
from receipt import ReceiptGenerator
from export import DataExporter

# ================= CONFIG =================
MODEL_PATH = r"E:\Project\Final\Software_part\runs\detect\veg_yolov8_final\weights\best.pt"
CAMERA_ID = 1
SERIAL_PORT = "COM5"
BAUDRATE = 9600
MIN_VALID_WEIGHT = 0.005

MAX_DETECTION_FRAMES = 10
MIN_VOTES_TO_LOCK = 3
SAVE_CONFIRMATION_MS = 2000

PRICE_PER_KG = {
    "potato": 40.0,
    "tomato": 70.0,
    "onion": 65.0,
    "chili": 160.0,
    "cucumber": 130.0
}
# =========================================


class SmartScaleApp:
    def __init__(self, window, window_title):
        self.window = window
        self.window.title(window_title)
        self.window.geometry("1200x700")
        self.window.configure(bg="#1e1e1e")

        # Data State
        self.current_prices = PRICE_PER_KG.copy()
        self.detected_veg = None
        self.current_weight = 0.0
        self.running = True

        # Session State
        self.session_active = False
        self.customer_info = {"name": "", "mobile": ""}

        # State Machine Variables
        self.state = "IDLE"
        self.locked_vegetable = None
        self.last_stable_weight = 0.0
        self.detection_votes = Counter()
        self.detection_frame_count = 0
        self.cart_items = []

        # --- DATABASE INIT ---
        try:
            self.db = Database()
        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to initialize database:\n{e}")
            self.window.destroy()
            return

        # --- RECEIPT GENERATOR INIT ---
        try:
            self.receipt_gen = ReceiptGenerator()
        except Exception as e:
            messagebox.showerror("Receipt Error", f"Failed to initialize receipt generator:\n{e}")
            self.window.destroy()
            return

        # --- DATA EXPORTER INIT ---
        try:
            self.exporter = DataExporter()
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to initialize data exporter:\n{e}")
            self.window.destroy()
            return

        # --- HARDWARE INIT ---
        self.init_hardware()

        # --- GUI LAYOUT ---
        self.create_gui()

        # --- Show customer form first ---
        self.show_customer_form()

        # --- START CAMERA LOOP ---
        self.update_loop()

    # ──────────────────────────────────────────────────────────
    # GUI CREATION
    # ──────────────────────────────────────────────────────────

    def create_gui(self):
        self.master_frame = tk.Frame(self.window, bg="#1e1e1e")
        self.master_frame.pack(fill=tk.BOTH, expand=True)

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

        btn_start = tk.Button(center, text="START BILLING",
                              font=("Segoe UI", 14, "bold"),
                              bg="#007acc", fg="white", relief="flat",
                              cursor="hand2", padx=30, pady=10,
                              command=self.start_session)
        btn_start.pack(pady=30)

        self.entry_name.bind("<Return>", lambda e: self.entry_mobile.focus())
        self.entry_mobile.bind("<Return>", lambda e: self.start_session())
        self.entry_name.focus_set()

    def build_main_screen(self):
        self.main_screen_frame = tk.Frame(self.master_frame, bg="#1e1e1e")
        self.main_screen_frame.pack(fill=tk.BOTH, expand=True)

        # Header
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

        # Content
        content = tk.Frame(self.main_screen_frame, bg="#1e1e1e")
        content.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Left Panel: Camera
        self.cam_frame = tk.Frame(content, bg="black", width=640, height=480)
        self.cam_frame.pack(side=tk.LEFT, padx=10)
        self.video_label = tk.Label(self.cam_frame, bg="black")
        self.video_label.pack()

        # Right Panel
        right_panel = tk.Frame(content, bg="#252526", width=400)
        right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)

        # A. Live Transaction
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

        # B. Cart
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

        # C. Price Editor
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

        # D. Finish Button
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

    def show_customer_form(self):
        for widget in self.master_frame.winfo_children():
            widget.destroy()
        self.session_active = False
        self.build_customer_form()

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

        # --- 1. SAVE TO DATABASE ---
        save_result = None
        if self.cart_items:
            try:
                save_result = self.db.save_session(self.customer_info, self.cart_items)
            except RuntimeError as e:
                messagebox.showerror("Database Error", str(e))
                return

        # --- 2. GENERATE PDF RECEIPT ---
        receipt_path = None
        if save_result:
            try:
                receipt_path = self.receipt_gen.generate(
                    self.customer_info,
                    self.cart_items,
                    save_result["session_id"]
                )
            except Exception as e:
                messagebox.showwarning("Receipt Warning",
                                       f"Data saved but receipt generation failed:\n{e}")

        # --- 3. EXPORT TO CSV + EXCEL ---
        export_result = None
        if save_result:
            try:
                export_result = self.exporter.export_all(
                    self.customer_info,
                    self.cart_items,
                    save_result["session_id"]
                )
            except Exception as e:
                messagebox.showwarning("Export Warning",
                                       f"Data saved but export failed:\n{e}")

        # --- 4. BUILD SUMMARY ---
        item_count = len(self.cart_items)
        grand_total = sum(item["total"] for item in self.cart_items)

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

        # Open the receipt PDF automatically
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
    # HARDWARE INIT
    # ──────────────────────────────────────────────────────────

    def init_hardware(self):
        try:
            self.reader = WeightReader(port=SERIAL_PORT, baudrate=BAUDRATE, buffer_size=3)
            self.reader.start()
        except Exception as e:
            messagebox.showerror("Error", f"Weight Reader Failed:\n{e}")
            self.window.destroy()
            return

        if not os.path.exists(MODEL_PATH):
            messagebox.showerror("Error", "YOLO Model file not found!")
            self.window.destroy()
            return
        self.model = YOLO(MODEL_PATH)
        self.class_names = self.model.names

        self.cap = cv2.VideoCapture(CAMERA_ID)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    def update_prices(self):
        try:
            for veg, entry in self.price_inputs.items():
                new_price = float(entry.get())
                self.current_prices[veg] = new_price
            messagebox.showinfo("Success", "Prices updated successfully!")
        except ValueError:
            messagebox.showerror("Error", "Invalid price format. Please enter numbers only.")

    # ──────────────────────────────────────────────────────────
    # CORE LOOP — State Machine
    # ──────────────────────────────────────────────────────────

    def update_loop(self):
        if not self.running:
            return

        if self.session_active:
            ret, frame = self.cap.read()
            if ret:
                raw = self.reader.get_weight(smoothed=True)
                self.current_weight = raw if raw and raw > MIN_VALID_WEIGHT else 0.0

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
    # ───────────────────────────────────���──────────────────────

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

        if self.detection_votes:
            top_class, top_count = self.detection_votes.most_common(1)[0]
            if top_count >= MIN_VOTES_TO_LOCK:
                self.locked_vegetable = top_class
                self.last_stable_weight = self.current_weight
                self.state = "LOCKED"
                self.lbl_status.config(text="LOCKED: " + top_class.upper(), fg="#00ff00")
                return

        if self.detection_frame_count >= MAX_DETECTION_FRAMES:
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
            # This prevents the dropping weight from overwriting the correct value
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
    # AUTO-SAVE LOGIC
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

        self.window.after(SAVE_CONFIRMATION_MS, self.reset_to_idle)

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
        if hasattr(self, 'cap'):
            self.cap.release()
        if hasattr(self, 'reader'):
            self.reader.stop()
        self.window.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = SmartScaleApp(root, "Vegetable POS System")
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()